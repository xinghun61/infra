// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"os"

	"github.com/ActiveState/tail"
	"github.com/luci/luci-go/common/logging"
)

// TailerOptions is passed to StartTailer.
type TailerOptions struct {
	// Path identifies a file to watch.
	Path string
	// PushBuffer knows how to forward log entries to the client.
	PushBuffer PushBuffer
	// Parser converts text lines into log entries, default is StdParser().
	Parser LogParser
	// Logger is used for local tailer own log messages.
	Logger logging.Logger
	// SeekToEnd is true to seek to the end of the file before tailing it.
	SeekToEnd bool
}

// Tailer watches a file for changes and pushes new lines to a the buffer.
type Tailer interface {
	// Stop notifies tailer goroutine to stop. Use buf.Stop() to wait for all
	// pending entries to be processed.
	Stop() error
	// Wait waits for the tailer to be in stopped state.
	Wait() error
	// Cleanup removes inotify watches added by the tailer.
	Cleanup()
}

// NewTailer spawn a goroutine that watches a file for changes and pushes
// new lines to the buffer.
func NewTailer(opts TailerOptions) (Tailer, error) {
	if opts.Parser == nil {
		opts.Parser = StdParser()
	}
	if opts.Logger == nil {
		opts.Logger = logging.Null()
	}
	var seekInfo *tail.SeekInfo
	if opts.SeekToEnd {
		seekInfo = &tail.SeekInfo{Offset: 0, Whence: os.SEEK_END}
	}
	tailer, err := tail.TailFile(opts.Path, tail.Config{
		Location:  seekInfo,
		ReOpen:    true,
		MustExist: false,
		Follow:    true,
		Logger:    tail.DiscardingLogger,
	})
	if err != nil {
		return nil, err
	}

	// tailer.Lines -> source -> PushBuffer (in drainChannel).
	source := make(chan string)
	go func() {
		defer close(source)
		for tailLine := range tailer.Lines {
			if tailLine.Err != nil {
				opts.Logger.Errorf("tail error: %s", tailLine.Err)
				continue
			}
			source <- tailLine.Text
		}
	}()
	go drainChannel(source, opts.Parser, opts.PushBuffer, opts.Logger)

	return tailer, nil
}
