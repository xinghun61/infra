// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPushBuffer(t *testing.T) {
	Convey("Noop run", t, func() {
		buf := NewPushBuffer(PushBufferOptions{})
		So(buf.Stop(nil), ShouldBeNil)
	})

	Convey("Send one, then stop", t, func() {
		cl := testclock.New(time.Time{})
		client := &fakeClient{clock: cl}
		buf := NewPushBuffer(PushBufferOptions{Client: client, Clock: cl})
		buf.Add(make([]Entry, 1))
		So(buf.Stop(nil), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
	})

	Convey("Send a big chunk to trigger immediate flush, then stop.", t, func() {
		cl := testclock.New(time.Time{})
		client := &fakeClient{clock: cl, ch: make(chan pushEntriesCall)}
		buf := NewPushBuffer(PushBufferOptions{
			Client:         client,
			Clock:          cl,
			FlushThreshold: 2,
		})
		buf.Add(make([]Entry, 4))
		select {
		case <-client.ch:
		case <-time.After(5 * time.Second): // use real clock to detect stuck queue
			t.Fatalf("Timeout while waiting for a flush")
		}
		cl.Add(time.Second)
		So(buf.Stop(nil), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
		So(client.getCalls()[0].ts, ShouldResemble, time.Time{}) // i.e. before Stop
	})

	Convey("Send a bunch of entries, wait for flush", t, func() {
		cl := testclock.New(time.Time{})
		client := &fakeClient{clock: cl, ch: make(chan pushEntriesCall)}
		buf := NewPushBuffer(PushBufferOptions{Client: client, Clock: cl})
		buf.Add(make([]Entry, 1))
		cl.Add(time.Second)
		buf.Add(make([]Entry, 1))

		// Spin time until flush is called.
		done := false
		for !done {
			select {
			case <-client.ch:
				done = true
			default:
				cl.Add(time.Second)
			}
		}

		So(buf.Stop(nil), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 1)
	})

	Convey("Retry works", t, func() {
		cl := testclock.New(time.Time{})
		cl.SetTimerCallback(func(clock.Timer) { cl.Add(1 * time.Second) })

		client := &fakeClient{brokenReplies: 4, clock: cl}
		buf := NewPushBuffer(PushBufferOptions{
			Client:          client,
			Clock:           cl,
			MaxPushAttempts: 10,
			PushRetryDelay:  1 * time.Second,
		})
		buf.Add(make([]Entry, 1))
		So(buf.Stop(nil), ShouldBeNil)
		So(len(client.getCalls()), ShouldEqual, 5) // 4 failures, 1 success
	})

	Convey("Gives up retrying", t, func() {
		cl := testclock.New(time.Time{})
		cl.SetTimerCallback(func(clock.Timer) { cl.Add(1 * time.Second) })

		client := &fakeClient{brokenReplies: 10000, clock: cl}
		buf := NewPushBuffer(PushBufferOptions{
			Client:          client,
			Clock:           cl,
			MaxPushAttempts: 5,
			PushRetryDelay:  1 * time.Second,
		})
		buf.Add(make([]Entry, 1))
		So(buf.Stop(nil), ShouldNotBeNil)
		So(len(client.calls), ShouldEqual, 5)
	})

	Convey("Stop timeout works", t, func() {
		startTs := time.Time{}
		cl := testclock.New(startTs)
		cl.SetTimerCallback(func(clock.Timer) { cl.Add(1 * time.Second) })

		client := &fakeClient{brokenReplies: 10000, clock: cl}
		buf := NewPushBuffer(PushBufferOptions{
			Client:          client,
			Clock:           cl,
			MaxPushAttempts: 5,
			PushRetryDelay:  100 * time.Second,
			StopTimeout:     1 * time.Second,
		})
		buf.Add(make([]Entry, 1))
		So(buf.Stop(nil), ShouldNotBeNil)
		So(len(client.calls), ShouldEqual, 1)
		So(cl.Now().Sub(startTs), ShouldBeLessThan, 100*time.Second)
	})
}

type pushEntriesCall struct {
	ts      time.Time
	entries []Entry
}

type fakeClient struct {
	clock         testclock.TestClock
	lock          sync.Mutex
	calls         []pushEntriesCall
	ch            chan pushEntriesCall
	brokenReplies int
}

func (c *fakeClient) PushEntries(entries []Entry) error {
	c.lock.Lock()
	defer c.lock.Unlock()
	call := pushEntriesCall{entries: entries}
	if c.clock != nil {
		call.ts = c.clock.Now()
	}
	c.calls = append(c.calls, call)
	if c.ch != nil {
		c.ch <- call
	}
	if c.brokenReplies > 0 {
		c.brokenReplies--
		return fmt.Errorf("broken")
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
