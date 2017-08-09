// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"bufio"
	"fmt"
	"io"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	droppedCounter = metric.NewCounter("cloudtail/pipe_drops",
		"Log entries read from a pipe and dropped because the sender couldn't keep up",
		nil,
		field.String("log"),
		field.String("resource_type"),
		field.String("resource_id"))
)

// PipeReader reads lines from io.Reader, parses and pushes them to the buffer.
type PipeReader struct {
	// ClientID identifies the log stream for monitoring.
	ClientID ClientID

	// Source is a reader to read logs from.
	Source io.Reader

	// PushBuffer knows how to forward log entries to the client.
	PushBuffer PushBuffer

	// Parser converts text lines into log entries, default is StdParser().
	Parser LogParser

	// LineBufferSize defines how many log lines to accumulate (if the flush is
	// blocked) before starting to drop them.
	//
	// Default is 0, which means to never drop lines (stop reading from the
	// source instead).
	LineBufferSize int

	// OnEOF is called immediately when EOF (or reading error) is encountered.
	//
	// Note that this happens before 'Run' returns, because 'Run' waits for data
	// to be pushed to the PushBuffer.
	OnEOF func()

	// OnLineDropped is called whenever a line gets dropped due to full buffer.
	OnLineDropped func()
}

// Run reads from the reader until EOF or until the context is closed.
//
// Returns error only if reading from io.Reader fails. On EOF or on context
// cancellation returns nil. Always returns same error as was sent to OnEOF.
//
// Waits for all read data to be pushed to PushBuffer.
func (r *PipeReader) Run(ctx context.Context) error {
	source := make(chan string, r.LineBufferSize)
	result := make(chan error, 1)

	go func() {
		scanner := bufio.NewScanner(r.Source)

		droppedTotal := 0
		droppedReport := 0
		nextDropReport := clock.Now(ctx).Add(time.Second)

		defer func() {
			if r.OnEOF != nil {
				r.OnEOF()
			}
			close(source)
			err := scanner.Err()
			if err == nil && droppedTotal != 0 {
				err = fmt.Errorf("%d lines in total were dropped due to insufficient line buffer size", droppedTotal)
			}
			result <- err
			close(result)
		}()

		logDropped := func(force bool) {
			if force || clock.Now(ctx).After(nextDropReport) {
				if droppedReport != 0 {
					logging.Warningf(ctx, "%d lines were dropped due to insufficient line buffer size", droppedReport)
					droppedReport = 0
				}
				nextDropReport = clock.Now(ctx).Add(time.Second)
			}
		}

		for scanner.Scan() {
			if r.LineBufferSize == 0 {
				select {
				case <-ctx.Done():
					return
				case source <- scanner.Text(): // Blocking.
				}
			} else {
				select {
				case <-ctx.Done():
					logDropped(true)
					return
				case source <- scanner.Text():
				default:
					// The buffer is full - drop this log line rather than blocking the pipe.
					droppedCounter.Add(ctx, 1, r.ClientID.LogID, r.ClientID.ResourceType, r.ClientID.ResourceID)
					droppedReport++
					droppedTotal++
					if r.OnLineDropped != nil {
						r.OnLineDropped()
					}
				}
				logDropped(false)
			}
		}
	}()

	drainChannel(ctx, source, r.Parser, r.PushBuffer)
	return <-result
}
