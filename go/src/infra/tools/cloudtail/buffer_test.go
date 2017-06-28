// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/retry/transient"
	"github.com/luci/luci-go/common/tsmon"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPushBuffer(t *testing.T) {
	Convey("with mocked time", t, func() {
		ctx := testContext()
		cl := clock.Get(ctx).(testclock.TestClock)
		cl.SetTimerCallback(func(d time.Duration, t clock.Timer) {
			if testclock.HasTags(t, "retry-timer") {
				cl.Add(d)
			}
		})

		Convey("Noop run", func() {
			buf := NewPushBuffer(PushBufferOptions{})
			buf.Start(ctx)
			So(buf.Stop(ctx), ShouldBeNil)
		})

		Convey("Send one, then stop", func() {
			client := &fakeClient{}
			buf := NewPushBuffer(PushBufferOptions{Client: client})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})
			So(buf.Stop(ctx), ShouldBeNil)
			So(len(client.getCalls()), ShouldEqual, 1)
		})

		Convey("Send a big chunk to trigger immediate flush, then stop.", func() {
			cl := clock.Get(ctx).(testclock.TestClock)
			client := &fakeClient{ch: make(chan pushEntriesCall)}
			buf := NewPushBuffer(PushBufferOptions{
				Client:         client,
				FlushThreshold: 2,
			})
			buf.Start(ctx)
			for i := 0; i < 4; i++ {
				buf.Send(ctx, Entry{})
			}
			client.drain(t, 4, 30*time.Second)
			cl.Add(time.Second) // to be able to distinguish flushes done during Stop
			So(buf.Stop(ctx), ShouldBeNil)
			So(len(client.getCalls()), ShouldEqual, 2)
			So(client.getCalls()[0].ts, ShouldResemble, testclock.TestRecentTimeUTC) // i.e. before Stop
		})

		Convey("Send an entry, wait for flush", func() {
			cl := clock.Get(ctx).(testclock.TestClock)
			cl.SetTimerCallback(func(d time.Duration, t clock.Timer) {
				if testclock.HasTags(t, "flush-timer") {
					cl.Add(d)
				}
			})

			client := &fakeClient{ch: make(chan pushEntriesCall)}
			buf := NewPushBuffer(PushBufferOptions{Client: client})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})

			// Wait until flush is called.
			<-client.ch

			// Make sure it happened by timer.
			So(cl.Now().Sub(testclock.TestRecentTimeUTC), ShouldEqual, DefaultFlushTimeout)

			So(buf.Stop(ctx), ShouldBeNil)
			So(len(client.getCalls()), ShouldEqual, 1)
		})

		Convey("Send some entries that should be merged into one", func() {
			client := &fakeClient{}
			buf := NewPushBuffer(PushBufferOptions{Client: client})
			buf.Start(ctx)
			buf.Send(ctx, Entry{TextPayload: "a", ParsedBy: NullParser()})
			buf.Send(ctx, Entry{TextPayload: "b"})
			So(buf.Stop(ctx), ShouldBeNil)
			So(len(client.getCalls()), ShouldEqual, 1)
			So(client.getEntries()[0].TextPayload, ShouldEqual, "a\nb")
		})

		Convey("Retry works", func() {
			client := &fakeClient{transientErrors: 4}
			buf := NewPushBuffer(PushBufferOptions{
				Client:          client,
				MaxPushAttempts: 10,
				PushRetryDelay:  500 * time.Millisecond,
			})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})
			So(buf.Stop(ctx), ShouldBeNil)
			So(len(client.getCalls()), ShouldEqual, 5) // 4 failures, 1 success
		})

		Convey("Gives up retrying after N attempts", func() {
			client := &fakeClient{transientErrors: 10000}
			buf := NewPushBuffer(PushBufferOptions{
				Client:          client,
				MaxPushAttempts: 5,
				PushRetryDelay:  500 * time.Millisecond,
			})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})
			So(buf.Stop(ctx), ShouldNotBeNil)
			So(len(client.calls), ShouldEqual, 5)
		})

		Convey("Gives up retrying on fatal errors", func() {
			client := &fakeClient{transientErrors: 5, fatalErrors: 1}
			buf := NewPushBuffer(PushBufferOptions{
				Client:          client,
				MaxPushAttempts: 500,
				PushRetryDelay:  500 * time.Millisecond,
			})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})
			So(buf.Stop(ctx), ShouldNotBeNil)
			So(len(client.calls), ShouldEqual, 6)
		})

		Convey("Stop timeout works", func() {
			withDeadline, _ := clock.WithTimeout(ctx, 20*time.Second)

			cl.SetTimerCallback(func(d time.Duration, t clock.Timer) {
				// "Freeze" time after deadline is reached. Otherwise the retry loop can
				// spin really fast (since the time is mocked) between 'buf.Send' and
				// 'buf.Stop'.
				runtime := clock.Now(ctx).Sub(testclock.TestRecentTimeUTC)
				if runtime <= 20*time.Second && testclock.HasTags(t, "retry-timer") {
					cl.Add(d)
				}
			})

			client := &fakeClient{transientErrors: 100000000}
			buf := NewPushBuffer(PushBufferOptions{
				Client:          client,
				MaxPushAttempts: 100000000,
				PushRetryDelay:  100 * time.Millisecond,
			})
			buf.Start(ctx)
			buf.Send(ctx, Entry{})
			So(buf.Stop(withDeadline), ShouldNotBeNil)
			So(clock.Now(ctx).Sub(testclock.TestRecentTimeUTC), ShouldBeLessThan, 30*time.Second)
		})
	})
}

func testContext() context.Context {
	ctx := context.Background()
	ctx, _ = testclock.UseTime(ctx, testclock.TestRecentTimeUTC)
	ctx, _ = tsmon.WithDummyInMemory(ctx)
	return ctx
}

type pushEntriesCall struct {
	ts      time.Time
	entries []Entry
}

type fakeClient struct {
	lock            sync.Mutex
	calls           []pushEntriesCall
	ch              chan pushEntriesCall
	transientErrors int
	fatalErrors     int
}

func (c *fakeClient) PushEntries(ctx context.Context, entries []*Entry) error {
	c.lock.Lock()
	defer c.lock.Unlock()
	cpy := make([]Entry, len(entries))
	for i, e := range entries {
		cpy[i] = *e
	}
	call := pushEntriesCall{entries: cpy}
	call.ts = clock.Now(ctx)
	c.calls = append(c.calls, call)
	if c.ch != nil {
		c.ch <- call
	}
	if c.transientErrors > 0 {
		c.transientErrors--
		return errors.New("transient error", transient.Tag)
	}
	if c.fatalErrors > 0 {
		c.fatalErrors--
		return fmt.Errorf("fatal error")
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

func (c *fakeClient) drain(t *testing.T, count int, timeout time.Duration) {
	deadline := time.After(timeout) // use real clock to detect stuck test
	total := 0
	for {
		select {
		case call := <-c.ch:
			total += len(call.entries)
			if total >= count {
				if total != count {
					t.Fatalf("Expected to process %d entries, processed %d", count, total)
				}
				return
			}
		case <-deadline:
			t.Fatalf("Timeout while waiting for a flush")
		}
	}
}
