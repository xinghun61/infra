// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
)

// Default config for PushBuffer if none is provided.
const (
	DefaultFlushThreshold = 1000
	DefaultFlushTimeout   = 5 * time.Second
)

// PushBufferOptions defines configuration for a new PushBuffer instance.
type PushBufferOptions struct {
	// Client is configured client to use to push messages.
	Client Client
	// Logger is local logger to use for cloudtail own local messages.
	Logger logging.Logger
	// Clock is useful in unittests.
	Clock clock.Clock
	// FlushThreshold defines how many pending messages trigger a flush.
	FlushThreshold int
	// FlushTimeout is maximum time an entry is kept in buffer before it is sent.
	FlushTimeout time.Duration
}

// PushBuffer batches log entries together before pushing them to the client.
type PushBuffer interface {
	// Add appends entries to the buffer. They all will be sent via logging
	// client eventually. Add can occasionally block, waiting for pending data to
	// be sent. It panics when called with a stopped buffer.
	Add(e ...Entry)
	// Stop waits for all entries to be sent and stops flush timer. It returns
	// a error if any of pending data wasn't successfully pushed. It panics if
	// called with already stopped buffer.
	Stop() error
}

// NewPushBuffer returns PushBuffer that's ready to accept log entries.
func NewPushBuffer(opts PushBufferOptions) PushBuffer {
	if opts.Logger == nil {
		opts.Logger = logging.Null()
	}
	if opts.Clock == nil {
		opts.Clock = clock.GetSystemClock()
	}
	if opts.FlushThreshold == 0 {
		opts.FlushThreshold = DefaultFlushThreshold
	}
	if opts.FlushTimeout == 0 {
		opts.FlushTimeout = DefaultFlushTimeout
	}
	buf := &pushBufferImpl{
		PushBufferOptions: opts,
		input:             make(chan []Entry),
		output:            make(chan error),
		timer:             opts.Clock.NewTimer(),
	}
	go buf.loop()
	return buf
}

////////////////////////////////////////////////////////////////////////////////

type pushBufferImpl struct {
	PushBufferOptions

	// Used from main goroutine and internal goroutine.
	input  chan []Entry
	output chan error

	// Used from internal goroutine only.
	pending  []Entry     // all unacknowledged entries
	lastErr  error       // last flush error, set in 'flush'
	timer    clock.Timer // flush timeout timer, gets reset in 'flush'
	timerSet bool        // true if timer was Reset and hasn't fired yet
}

func (b *pushBufferImpl) Add(e ...Entry) {
	if len(e) != 0 {
		b.input <- e
	}
}

func (b *pushBufferImpl) Stop() error {
	close(b.input)
	return <-b.output
}

////////////////////////////////////////////////////////////////////////////////

// loop runs internal flush loop as a separate goroutine.
func (b *pushBufferImpl) loop() {
	defer func() {
		if len(b.pending) != 0 {
			b.Logger.Errorf("dropping %d log entries", len(b.pending))
		}
		b.output <- b.lastErr
		close(b.output)
	}()

	alive := true
	for alive {
		var chunk []Entry
		select {
		case chunk, alive = <-b.input:
			if len(chunk) != 0 {
				b.pending = append(b.pending, chunk...)
				if len(b.pending) >= b.FlushThreshold {
					b.flush()
				}
				// Have pending data? Make sure it's flushed by timeout.
				if len(b.pending) > 0 && !b.timerSet {
					b.timer.Reset(b.FlushTimeout)
					b.timerSet = true
				}
			}
		case <-b.timer.GetC():
			b.flush()
		}
	}
	b.flush()
}

// flush sends all buffered entries via client and stops flush timeout timer.
// It stops the timer even if flush failed (so restart the timer if needed).
func (b *pushBufferImpl) flush() {
	b.timer.Stop()
	b.timerSet = false
	if len(b.pending) == 0 {
		return
	}
	b.Logger.Debugf("flushing %d entries...", len(b.pending))
	if b.lastErr = b.Client.PushEntries(b.pending); b.lastErr != nil {
		// Don't clear pending. All messages will be resent on a next flush.
		// TODO(vadimsh): Chunk giant b.pending into several push calls.
		b.Logger.Errorf("%s", b.lastErr)
	} else {
		b.pending = nil
	}
}
