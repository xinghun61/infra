// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"io/ioutil"
	"os"
	"path/filepath"
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
	// (including inotify subsystem, or whatever github.com/ActiveState/tail
	// library is using on the current platform).
	Convey("Works", t, func(c C) {
		// Use buffered channel to avoid deadlocking if something goes wrong.
		client := &fakeClient{ch: make(chan pushEntriesCall, 100)}
		buf := NewPushBuffer(PushBufferOptions{Client: client, FlushTimeout: 1 * time.Millisecond})

		dir, err := ioutil.TempDir("", "cloudtail_test")
		So(err, ShouldBeNil)
		defer os.RemoveAll(dir)
		filePath := filepath.Join(dir, "tailed")

		putLine := func(line string, wait bool) {
			f, err := os.OpenFile(filePath, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0600)
			c.So(err, ShouldBeNil)
			_, err = f.Seek(0, os.SEEK_END)
			c.So(err, ShouldBeNil)
			_, err = f.WriteString(line + "\n")
			c.So(err, ShouldBeNil)
			c.So(f.Sync(), ShouldBeNil)
			c.So(f.Close(), ShouldBeNil)

			// Wait for this line to be consumed by tailer.
			if wait {
				<-client.ch
			}
		}

		tailer, err := NewTailer(TailerOptions{
			Path:       filePath,
			Parser:     NullParser(),
			PushBuffer: buf,
		})
		So(err, ShouldBeNil)
		defer CleanupTailer()

		putLine("line", true)
		putLine("   ", false)
		putLine("  another", true)
		putLine("", false)
		putLine("last one", true)

		So(tailer.Stop(), ShouldBeNil)
		So(buf.Stop(), ShouldBeNil)

		text := []string{}
		for _, e := range client.getEntries() {
			text = append(text, e.TextPayload)
		}
		So(text, ShouldResemble, []string{"line", "another", "last one"})
	})
}
