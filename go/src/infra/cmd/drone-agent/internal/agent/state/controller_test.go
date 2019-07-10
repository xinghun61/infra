// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state

import (
	"errors"
	"testing"
	"time"

	"infra/cmd/drone-agent/internal/bot"
)

func TestController(t *testing.T) {
	t.Parallel()
	t.Run("happy path", func(t *testing.T) {
		t.Parallel()
		b := bot.NewFakeBot()
		started := make(chan string, 1)
		released := make(chan string, 1)
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				started <- dutID
				return b, nil
			},
			release: func(dutID string) { released <- dutID },
		}
		c := NewController(h)

		const d = "some-dut"
		c.AddDUT(d)
		select {
		case got := <-started:
			if got != d {
				t.Errorf("Got started bot %v; want %v", got, d)
			}
		case <-time.After(time.Second):
			t.Fatalf("bot not started after adding DUT")
		}

		c.DrainDUT(d)
		c.Wait()
		select {
		case got := <-released:
			if got != d {
				t.Errorf("Got released bot %v; want %v", got, d)
			}
		default:
			t.Fatalf("bot not released after draining DUT")
		}
	})
	t.Run("restart bot if crash", func(t *testing.T) {
		t.Parallel()
		started := make(chan *bot.FakeBot, 1)
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				b := bot.NewFakeBot()
				started <- b
				return b, nil
			},
		}
		c := NewController(h)
		defer c.Wait()

		const d = "some-dut"
		c.AddDUT(d)
		defer c.TerminateDUT(d)
		b := <-started
		b.Stop()
		select {
		case <-started:
		case <-time.After(time.Millisecond):
			t.Fatalf("bot not restarted after stopping")
		}
	})
	t.Run("can drain DUT even if starting errors", func(t *testing.T) {
		t.Parallel()
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				return nil, errors.New("some error")
			},
		}
		c := NewController(h)
		const d = "some-dut"
		c.AddDUT(d)
		c.DrainDUT(d)
		// This will hang if draining doesn't work.
		c.Wait()
	})
	t.Run("stopped DUTs are removed", func(t *testing.T) {
		t.Parallel()
		c := NewController(stubHook{})
		c.AddDUT("ionasal")
		c.DrainDUT("ionasal")
		c.Wait()
		got := c.duts
		if len(got) > 0 {
			t.Errorf("Got running DUTs %v; want none", got)
		}
	})
	t.Run("drain all does not hang", func(t *testing.T) {
		t.Parallel()
		c := NewController(stubHook{})
		c.AddDUT("ionasal")
		c.AddDUT("nero")
		// This will hang if DrainAll locks improperly.
		c.DrainAll()
		c.Wait()
	})
	t.Run("terminate all does not hang", func(t *testing.T) {
		t.Parallel()
		c := NewController(stubHook{})
		c.AddDUT("ionasal")
		c.AddDUT("nero")
		// This will hang if TerminateAll locks improperly.
		c.TerminateAll()
		c.Wait()
	})
}

// stubHook is an implementation of ControllerHook for tests.
type stubHook struct {
	start   func(string) (bot.Bot, error)
	release func(string)
}

func (h stubHook) StartBot(dutID string) (bot.Bot, error) {
	if f := h.start; f != nil {
		return f(dutID)
	}
	return bot.NewFakeBot(), nil
}

func (h stubHook) ReleaseDUT(dutID string) {
	if f := h.release; f != nil {
		f(dutID)
	}
}
