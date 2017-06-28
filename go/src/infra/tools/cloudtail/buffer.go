// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"sync/atomic"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry/transient"
)

// Default config for PushBuffer if none is provided.
const (
	DefaultFlushThreshold  = 5000
	DefaultFlushTimeout    = 5 * time.Second
	DefaultMaxPushAttempts = 5
	DefaultPushRetryDelay  = 500 * time.Millisecond
)

// PushBufferOptions defines configuration for a new PushBuffer instance.
type PushBufferOptions struct {
	// Client is configured client to use to push messages.
	//
	// Required.
	Client Client

	// FlushThreshold defines how many pending messages trigger a flush.
	FlushThreshold int

	// FlushTimeout is maximum time an entry is kept in buffer before it is sent.
	FlushTimeout time.Duration

	// MaxPushAttempts is how many times to push entries when retrying errors.
	MaxPushAttempts int

	// PushRetryDelay is how long to wait before retrying a failed push.
	//
	// Will be doubled on each failed retry attempt.
	PushRetryDelay time.Duration
}

// PushBuffer batches log entries together before pushing them to the client.
//
// It accumulates entries in a buffer and flushes them when the buffer is full
// (see FlushThreshold option) or when the first pushed entry is sufficiently
// old (see FlushTimeout option).
//
// It uses no more than 1 connection to the Cloud Logging.
type PushBuffer interface {
	// Start starts an internal goroutine that periodically flushes entries.
	//
	// The goroutine uses the given context for creating timers and for flushes.
	// If this context is canceled, all incoming entries are dropped. Instead use
	// Stop to shutdown gracefully.
	Start(ctx context.Context)

	// Send appends the entry to the buffer of pending entries and flushes them if
	// the buffer becomes full.
	//
	// It can block, waiting for pending data to be sent. Unblocks (and drops
	// the entry) if the context is canceled.
	//
	// Since flushes may happen asynchronously, doesn't return an error. Instead
	// a failed flush attempt will be logged and the error will eventually be
	// returned by Stop().
	Send(ctx context.Context, e Entry)

	// Stop waits for all entries to be sent and stops the flush timer.
	//
	// Aborts ASAP when the passed context is canceled. Returns an error if any of
	// pending data wasn't flushed successfully.
	Stop(ctx context.Context) error
}

// NewPushBuffer returns PushBuffer that's ready to accept log entries.
func NewPushBuffer(opts PushBufferOptions) PushBuffer {
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
	return &pushBufferImpl{PushBufferOptions: opts}
}

////////////////////////////////////////////////////////////////////////////////

type pushBufferImpl struct {
	PushBufferOptions

	// Used from main goroutine and internal goroutine.
	input   chan *Entry
	output  chan error
	dropped uint32 // updated atomically

	// Used from internal goroutine only.
	pending        []*Entry      // all unacknowledged entries
	lastErr        error         // non nil if some flush failed, set in 'flush'
	timer          clock.Timer   // flush timeout timer, gets reset in 'flush'
	timerSet       bool          // true if timer was Reset and hasn't fired yet
	stopCh         chan struct{} // signals that retry loop should die
	lastDropReport time.Time     // time when logDrop did something
}

func (b *pushBufferImpl) Start(ctx context.Context) {
	if b.input != nil {
		panic("Start was already called")
	}
	b.input = make(chan *Entry, 500)
	b.output = make(chan error)
	b.timer = clock.NewTimer(clock.Tag(ctx, "flush-timer"))
	b.stopCh = make(chan struct{})
	b.lastDropReport = clock.Now(ctx)
	go b.loop(ctx)
}

func (b *pushBufferImpl) Send(ctx context.Context, e Entry) {
	if b.input == nil {
		panic("Start wasn't called yet")
	}
	select {
	case b.input <- &e: // send a pointer to the copy
	case <-ctx.Done():
		b.recordDrop(ctx, 1)
	}
}

func (b *pushBufferImpl) Stop(ctx context.Context) error {
	close(b.input) // panics if already closed

	killer := make(chan struct{})
	defer close(killer)

	go func() {
		select {
		case <-ctx.Done(): // halt the flush on context cancellation
		case <-killer: // don't leak this goroutine on successful flush
		}
		close(b.stopCh)
	}()

	return <-b.output
}

////////////////////////////////////////////////////////////////////////////////

// recordDrop counts how many entries were dropped.
func (b *pushBufferImpl) recordDrop(ctx context.Context, count int) {
	// TODO(vadimsh): Report to the monitoring.
	if count != 0 {
		atomic.AddUint32(&b.dropped, uint32(count))
	}
}

func (b *pushBufferImpl) logDrop(ctx context.Context, final bool) {
	// Throttle frequency of reports.
	now := clock.Now(ctx)
	if !final && now.Sub(b.lastDropReport) < time.Second {
		return
	}
	b.lastDropReport = now

	// Log and reset the counter.
	dropped := atomic.SwapUint32(&b.dropped, 0)
	if dropped != 0 {
		logging.Warningf(ctx, "Dropped %d log entries due to errors or timeouts", dropped)
	}
}

// loop runs internal flush loop as a separate goroutine.
func (b *pushBufferImpl) loop(ctx context.Context) {
	defer func() {
		b.recordDrop(ctx, len(b.pending))
		b.logDrop(ctx, true)
		b.output <- b.lastErr
		close(b.output)
	}()

outer:
	for {
		// Occasionally log how many entries have been dropped due to errors.
		// This also happens in 'flush'.
		b.logDrop(ctx, false)

		select {
		case entry, alive := <-b.input:
			if !alive {
				break outer
			}
			b.addToPending(ctx, entry)

			// Grab all we have buffered there.
			spin := true
			for spin {
				select {
				case entry, spin = <-b.input:
					if entry != nil {
						b.addToPending(ctx, entry)
					}
				default:
					spin = false
				}
			}

			// Still have pending data? Make sure it's flushed eventually by timeout.
			if len(b.pending) > 0 && !b.timerSet {
				b.timer.Reset(b.FlushTimeout)
				b.timerSet = true
			}

		case <-b.timer.GetC():
			b.flush(ctx)
		}
	}

	// The final flush.
	b.flush(ctx)
}

// addToPending adds entry to pending buffer, flushing it if it's full.
func (b *pushBufferImpl) addToPending(ctx context.Context, entry *Entry) {
	b.pending = append(b.pending, entry)
	if len(b.pending) >= b.FlushThreshold {
		b.flush(ctx) // drops them if the context is already canceled
	}
}

// mergeEntries uses parser's MergeLogLine to combine a bunch of sequential
// log entries into one, if appropriate.
//
// Mutates b.pending in place.
func (b *pushBufferImpl) mergeEntries() {
	merged := make([]*Entry, 0, len(b.pending))

	for i, e := range b.pending {
		// Always skip the first one - there's nothing to merge it into.
		if i == 0 {
			merged = append(merged, e)
			continue
		}

		last := merged[len(merged)-1]

		// This literally means: if 'e' wasn't recognized by a parser, but 'last'
		// was, try to merge 'e' into 'last'. Otherwise keep 'e' as a standalone
		// entry.
		if e.ParsedBy == nil && last.ParsedBy != nil && last.ParsedBy.MergeLogLine(e.TextPayload, last) {
			continue
		} else {
			merged = append(merged, e)
		}
	}

	b.pending = merged
}

// flush sends all buffered entries and stops the flush timeout timer.
func (b *pushBufferImpl) flush(ctx context.Context) {
	// The flush timer will be restarted next time we have an item in the buffer.
	if b.timerSet {
		b.timer.Stop()
		b.timerSet = false
	}
	if len(b.pending) == 0 {
		return
	}

	b.mergeEntries()

	// Don't even try to flush if the context is canceled already.
	if err := ctx.Err(); err != nil {
		b.lastErr = err
		b.recordDrop(ctx, len(b.pending))
		b.pending = nil
		return
	}

	// Give up trying to flush as soon as b.stopCh is closed.
	ctx, cancel := context.WithCancel(ctx)
	go func() {
		select {
		case <-b.stopCh:
			cancel()
		case <-ctx.Done():
		}
	}()
	defer cancel() // to terminate 'go func()' above

	// Push all that we have. This respects context deadline and cancellation.
	logging.Debugf(ctx, "flushing %d entries...", len(b.pending))
	if err := b.pushWithRetries(ctx, b.pending); err != nil {
		b.lastErr = err
		b.recordDrop(ctx, len(b.pending))
		logging.WithError(err).Warningf(ctx, "Failed to send %d entries", len(b.pending))
	}
	b.pending = nil

	// Occasionally log how many entries have been dropped due to errors.
	b.logDrop(ctx, false)
}

// pushWithRetries sends messages through the client.
//
// It retries on errors at most MaxPushAttempts number of times or until the
// context is canceled.
func (b *pushBufferImpl) pushWithRetries(ctx context.Context, entries []*Entry) error {
	attempt := 0
	delay := b.PushRetryDelay
	for {
		attempt++
		err := b.Client.PushEntries(ctx, entries)
		switch {
		case err == nil:
			return nil
		case ctx.Err() != nil:
			return ctx.Err()
		case attempt >= b.MaxPushAttempts || !transient.Tag.In(err):
			return err
		}
		logging.WithError(err).Warningf(ctx, "failed to send %d entries, retrying in %s...", len(entries), delay)
		select {
		case res := <-clock.After(clock.Tag(ctx, "retry-timer"), delay):
			if res.Err != nil {
				return res.Err // the context was canceled
			}
			delay *= 2
			// Safeguard against an overflow in unit tests.
			if delay > 30*time.Minute {
				delay = 30 * time.Minute
			}
		}
	}
}
