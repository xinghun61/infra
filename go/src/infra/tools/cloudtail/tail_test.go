// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTailer(t *testing.T) {
	// This test creates a file, writes a line to it, waits for the line to be
	// read by tailer and sent via mocked client, then writes another one, etc.
	// If something goes wrong the test fails in two possible ways:
	//   * Timeout if number of tailed lines is less than expected.
	//   * ShouldResemble failure when comparing final results if number of tailed
	//     lines is more than expected.
	// The channel is needed to provide synchronization for internal file system
	// buffers: this test invokes full round trip through file system guts
	// (including inotify subsystem, or whatever fsnotify library is using on
	// the current platform).

	Convey("Dumb poller works", t, func(c C) {
		runTest(c, TailerOptions{
			UsePolling:    true,
			PollingPeriod: 10 * time.Millisecond,
		})
	})

	Convey("Fsnotify poller works", t, func(c C) {
		runTest(c, TailerOptions{
			UsePolling: false,
		})
	})
}

func runTest(c C, opts TailerOptions) {
	// Use buffered channel to avoid deadlocking if something goes wrong.
	client := &fakeClient{ch: make(chan pushEntriesCall, 100)}
	buf := NewPushBuffer(PushBufferOptions{Client: client, FlushTimeout: 1 * time.Millisecond})

	dir, err := ioutil.TempDir("", "cloudtail_test")
	So(err, ShouldBeNil)
	defer os.RemoveAll(dir)
	filePath := filepath.Join(dir, "tailed")

	totalExpected := 0
	putData := func(expected int, data string) {
		f, err := os.OpenFile(filePath, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0600)
		c.So(err, ShouldBeNil)
		_, err = f.Seek(0, os.SEEK_END)
		c.So(err, ShouldBeNil)
		_, err = f.WriteString(data)
		c.So(err, ShouldBeNil)
		c.So(f.Sync(), ShouldBeNil)
		c.So(f.Close(), ShouldBeNil)

		// Wait for this data to be consumed by tailer.
		totalExpected += expected
		for expected != 0 {
			consumed := <-client.ch
			c.So(len(consumed.entries), ShouldBeLessThanOrEqualTo, expected)
			expected -= len(consumed.entries)
		}
	}

	truncateFile := func() {
		So(os.Truncate(filePath, 0), ShouldBeNil)
	}

	rotateFile := func() {
		c.So(os.Rename(filePath, filePath+".1"), ShouldBeNil)
	}

	deleteFile := func() {
		c.So(os.Remove(filePath), ShouldBeNil)

		// On Windows if deleted file still has open handles, new one can't be
		// created in its place. Wait until tailer closes its handle. Daemons that
		// rotate logs have to deal with it too :-/
		if runtime.GOOS == "windows" {
			deadline := time.Now().Add(2 * time.Second)
			var lastErr error
			for time.Now().Before(deadline) {
				var f *os.File
				f, lastErr = os.OpenFile(filePath, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0600)
				if f != nil {
					f.Close()
					break
				}
				time.Sleep(10 * time.Millisecond)
			}
			So(lastErr, ShouldBeNil)
		}
	}

	// Put some lines to be skipped due to 'SeekToEnd: true'.
	putData(0, "skipped line 1\nskipped line 2\n")

	initializedSignal := make(chan struct{})

	// Use small RotationCheckPeriod to detect file truncation faster. This
	// timer is the only mechanism that correctly detects truncation.
	opts.Path = filePath
	opts.Parser = NullParser()
	opts.PushBuffer = buf
	opts.SeekToEnd = true
	opts.RotationCheckPeriod = 50 * time.Millisecond
	opts.initializedSignal = initializedSignal
	tailer, err := NewTailer(opts)
	So(err, ShouldBeNil)
	<-initializedSignal

	manyLines := strings.Repeat("manylines\n", 1000)
	bigLine := strings.Repeat("bigline", 1000)

	putData(1, "line\n")
	putData(0, "   \n")
	putData(1, "  another\n")
	truncateFile()
	putData(1, "truncated\n")
	putData(0, "\n")
	rotateFile()
	putData(1, "rotated\n")
	deleteFile()
	putData(1, "deleted\n")
	putData(1, "last one\n")
	putData(0, "")
	putData(1000, manyLines)
	putData(1, bigLine+"\n")

	So(tailer.Stop(), ShouldBeNil)
	So(tailer.Wait(), ShouldBeNil)
	So(buf.Stop(nil), ShouldBeNil)

	text := []string{}
	for _, e := range client.getEntries() {
		text = append(text, e.TextPayload)
	}
	So(len(text), ShouldEqual, totalExpected)
	So(text[:6], ShouldResemble, []string{"line", "another", "truncated", "rotated", "deleted", "last one"})
}
