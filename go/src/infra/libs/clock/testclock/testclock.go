// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testclock

import (
	"sync"
	"time"

	"infra/libs/clock"
)

// TestClock is a Clock interface with additional methods to help instrument it.
type TestClock interface {
	clock.Clock
	Set(time.Time)
	Add(time.Duration)
	SetTimerCallback(TimerCallback)
}

// TimerCallback that can be invoked when a timer has been set. This is useful
// for sychronizing state when testing.
type TimerCallback func(clock.Timer)

type cancelFunc func()

// testClock is a test-oriented implementation of the 'Clock' interface.
//
// This implementation's Clock responses are configurable by modifying its
// member variables. Time-based events are explicitly triggered by sending on a
// Timer instance's channel.
type testClock struct {
	sync.RWMutex

	now       time.Time  // The current clock time.
	timerCond *sync.Cond // Condition used to manage timer blocking.

	timerCallback TimerCallback // Optional callback when a timer has been set.
}

var _ TestClock = (*testClock)(nil)

// New returns a TestClock instance set at the specified time.
func New(now time.Time) TestClock {
	c := testClock{
		now: now,
	}
	c.timerCond = sync.NewCond(&c)
	return &c
}

func (c *testClock) Now() time.Time {
	c.RLock()
	defer c.RUnlock()

	return c.now
}

func (c *testClock) Sleep(d time.Duration) {
	<-c.After(d)
}

func (c *testClock) NewTimer() clock.Timer {
	return newTimer(c)
}

func (c *testClock) After(d time.Duration) <-chan time.Time {
	t := c.NewTimer()
	t.Reset(d)
	return t.GetC()
}

func (c *testClock) Set(t time.Time) {
	c.Lock()
	defer c.Unlock()

	c.setTimeLocked(t)
}

func (c *testClock) Add(d time.Duration) {
	c.Lock()
	defer c.Unlock()

	c.setTimeLocked(c.now.Add(d))
}

func (c *testClock) setTimeLocked(t time.Time) {
	if t.Before(c.now) {
		panic("Cannot go backwards in time. You're not Doc Brown.")
	}
	c.now = t

	// Unblock any blocking timers that are waiting on our lock.
	c.pokeTimers(true)
}

func (c *testClock) SetTimerCallback(callback TimerCallback) {
	c.Lock()
	defer c.Unlock()

	c.timerCallback = callback
}

func (c *testClock) getTimerCallback() TimerCallback {
	c.Lock()
	defer c.Unlock()

	return c.timerCallback
}

func (c *testClock) signalTimerSet(t clock.Timer) {
	callback := c.getTimerCallback()
	if callback != nil {
		callback(t)
	}
}

func (c *testClock) pokeTimers(locked bool) {
	if !locked {
		c.Lock()
		defer c.Unlock()
	}

	c.timerCond.Broadcast()
}

// invokeAt invokes the specified callback when the Clock has advanced at
// or after the specified threshold.
//
// The returned cancelFunc can be used to cancel the blocking. If the cancel
// function is invoked before the callback, the callback will not be invoked.
func (c *testClock) invokeAt(threshold time.Time, callback func(time.Time)) cancelFunc {
	stopC := make(chan struct{})
	finishedC := make(chan struct{})

	// Our control goroutine will monitor both time and stop signals. It will only
	// terminate when stopC has been closed.
	//
	// The lock that we take our here is owned by the following goroutine.
	c.Lock()
	go func() {
		defer func() {
			now := c.now
			c.Unlock()
			close(finishedC)
			callback(now)
		}()

		for {
			// Determine if we are past our signalling threshold. We can safely access
			// our clock's time member directly, since we hold its lock from the
			// condition firing.
			if !c.now.Before(threshold) {
				return
			}

			// Wait for a signal from our clock's condition.
			c.timerCond.Wait()

			// Have we been stopped?
			select {
			case <-stopC:
				return

			default:
				// Nope.
			}
		}
	}()

	return func() {
		// Close our stop channel and block pending goroutine termination.
		close(stopC)
		c.pokeTimers(false)
		<-finishedC
	}
}
