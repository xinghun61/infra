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
	DefaultFlushThreshold  = 1000
	DefaultFlushTimeout    = 5 * time.Second
	DefaultMaxPushAttempts = 100
	DefaultPushRetryDelay  = 1 * time.Second
	DefaultStopTimeout     = 10 * time.Second
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
	// MaxPushAttempts is how many times to push entries when retrying errors.
	MaxPushAttempts int
	// PushRetryDelay is how long to wait before retrying a failed push.
	PushRetryDelay time.Duration
	// StopTimeout is how long to wait for Stop to flush pending data.
	StopTimeout time.Duration
}

// PushBuffer batches log entries together before pushing them to the client.
type PushBuffer interface {
	// Add appends entries to the buffer. They all will be sent via logging
	// client eventually. Add can occasionally block, waiting for pending data to
	// be sent. It panics when called with a stopped buffer.
	Add(e ...Entry)
	// Stop waits for all entries to be sent and stops flush timer. It returns
	// a error if any of pending data wasn't successfully pushed. It panics if
	// called with already stopped buffer. It accepts a channel that can be
	// signaled to abort any pending operations ASAP. The passed channel can
	// be nil.
	Stop(abort <-chan struct{}) error
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
	if opts.MaxPushAttempts == 0 {
		opts.MaxPushAttempts = DefaultMaxPushAttempts
	}
	if opts.PushRetryDelay == 0 {
		opts.PushRetryDelay = DefaultPushRetryDelay
	}
	if opts.StopTimeout == 0 {
		opts.StopTimeout = DefaultStopTimeout
	}
	buf := &pushBufferImpl{
		PushBufferOptions: opts,
		input:             make(chan []Entry),
		output:            make(chan error),
		timer:             opts.Clock.NewTimer(),
		stopCh:            make(chan struct{}, 1),
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
	pending  []Entry       // all unacknowledged entries
	lastErr  error         // last flush error, set in 'flush'
	timer    clock.Timer   // flush timeout timer, gets reset in 'flush'
	timerSet bool          // true if timer was Reset and hasn't fired yet
	stopCh   chan struct{} // signals that retry loop should die
}

func (b *pushBufferImpl) Add(e ...Entry) {
	if len(e) != 0 {
		b.input <- e
	}
}

func (b *pushBufferImpl) Stop(abort <-chan struct{}) error {
	close(b.input)
	go func() {
		select {
		case <-abort:
		case <-b.Clock.After(b.StopTimeout):
		}
		close(b.stopCh)
	}()
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
	if err := b.pushWithRetries(b.pending); err != nil {
		b.Logger.Errorf("dropping %d entries, flush failed - %s", len(b.pending), err)
		b.lastErr = err
	}
	b.pending = nil
}

// pushWithRetries sends messages through the client, retrying on errors
// MaxPushAttempts number of times before giving up.
func (b *pushBufferImpl) pushWithRetries(entries []Entry) error {
	attempt := 0
	for {
		attempt++
		err := b.Client.PushEntries(entries)
		if err == nil {
			return nil
		}
		if attempt >= b.MaxPushAttempts {
			return err
		}
		b.Logger.Errorf("failed to send %d entries (%s), retrying...", len(entries), err)
		select {
		case <-b.stopCh:
			return err
		case <-b.Clock.After(b.PushRetryDelay):
		}
	}
}
