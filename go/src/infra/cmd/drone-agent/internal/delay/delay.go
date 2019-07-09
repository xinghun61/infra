// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package delay implements a delayable timer.
package delay

import (
	"context"
	"sync"
	"time"
)

// Timer is a delayable timer.  The time cannot be delayed or reused
// after it fires.
type Timer struct {
	m     sync.Mutex
	timer *time.Timer
}

// NewTimer returns a new Timer.
func NewTimer(t time.Time) *Timer {
	return &Timer{
		timer: time.NewTimer(t.Sub(time.Now())),
	}
}

// C returns the timer channel, like for time.Timer.
func (t *Timer) C() <-chan time.Time {
	return t.timer.C
}

// Set sets a new expiration time for the Timer.  This method is safe
// to call concurrently.
//
// Usually, the new time will be after the old time.
//
// If the timer already fired, then this call does nothing.
func (t *Timer) Set(new time.Time) {
	t.m.Lock()
	defer t.m.Unlock()
	if !t.timer.Stop() {
		// Timer already fired.
		return
	}
	t.timer.Reset(new.Sub(time.Now()))
}

// Stop stops the timer from firing if it has not already.  The timer
// cannot be reused afterward.  This method is idempotent.
func (t *Timer) Stop() {
	t.m.Lock()
	t.timer.Stop()
	t.m.Unlock()
}

// WithTimer returns a context that is canceled when a delayable timer
// fires.
//
// Note that the returned timer's channel should not be used; only the
// Set/Stop methods should be used.
func WithTimer(ctx context.Context, t time.Time) (context.Context, *Timer) {
	ctx, f := context.WithCancel(ctx)
	tmr := NewTimer(t)
	go func() {
		select {
		case <-ctx.Done():
			tmr.Stop()
		case <-tmr.C():
		}
		f()
	}()
	return ctx, tmr
}
