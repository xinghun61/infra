// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPushBuffer(t *testing.T) {
	Convey("Noop run", t, func() {
		buf := NewPushBuffer(PushBufferOptions{})
		So(buf.Stop(), ShouldBeNil)
	})

	Convey("Send one, then stop", t, func() {
		clock := testclock.New(time.Time{})
		client := &fakeClient{clock: clock}
		buf := NewPushBuffer(PushBufferOptions{Client: client, Clock: clock})
		buf.Add(Entry{})
		So(buf.Stop(), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
	})

	Convey("Send a big chunk to trigger immediate flush, then stop.", t, func() {
		clock := testclock.New(time.Time{})
		client := &fakeClient{clock: clock}
		buf := NewPushBuffer(PushBufferOptions{
			Client:         client,
			Clock:          clock,
			FlushThreshold: 2,
		})
		buf.Add(Entry{}, Entry{}, Entry{}, Entry{})
		clock.Add(time.Second)
		So(buf.Stop(), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
		So(client.getCalls()[0].ts, ShouldResemble, time.Time{}) // i.e. before Stop
	})

	Convey("Send a bunch of entries, wait for flush", t, func() {
		clock := testclock.New(time.Time{})
		client := &fakeClient{clock: clock, ch: make(chan pushEntriesCall)}
		buf := NewPushBuffer(PushBufferOptions{Client: client, Clock: clock})
		buf.Add(Entry{})
		clock.Add(time.Second)
		buf.Add(Entry{})

		// Spin time until flush is called.
		done := false
		for !done {
			select {
			case <-client.ch:
				done = true
			default:
				clock.Add(time.Second)
			}
		}

		So(buf.Stop(), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
	})

	Convey("Handles client errors", t, func() {
		clock := testclock.New(time.Time{})
		client := &fakeClient{clock: clock, broken: true}
		buf := NewPushBuffer(PushBufferOptions{Client: client, Clock: clock})
		buf.Add(Entry{})
		So(buf.Stop(), ShouldNotBeNil)
	})
}

type pushEntriesCall struct {
	ts      time.Time
	entries []Entry
}

type fakeClient struct {
	clock  testclock.TestClock
	lock   sync.Mutex
	calls  []pushEntriesCall
	ch     chan pushEntriesCall
	broken bool
}

func (c *fakeClient) PushEntries(entries []Entry) error {
	c.lock.Lock()
	defer c.lock.Unlock()
	if c.broken {
		return fmt.Errorf("broken")
	}
	call := pushEntriesCall{entries: entries}
	if c.clock != nil {
		call.ts = c.clock.Now()
	}
	c.calls = append(c.calls, call)
	if c.ch != nil {
		c.ch <- call
	}
	return nil
}

func (c *fakeClient) getCalls() []pushEntriesCall {
	c.lock.Lock()
	defer c.lock.Unlock()
	return c.calls
}

func (c *fakeClient) getEntries() []Entry {
	c.lock.Lock()
	defer c.lock.Unlock()
	out := []Entry{}
	for _, call := range c.calls {
		out = append(out, call.entries...)
	}
	return out
}
