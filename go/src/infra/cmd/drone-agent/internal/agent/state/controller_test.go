// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state

import (
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/google/go-cmp/cmp"

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
	t.Run("active DUTs", func(t *testing.T) {
		t.Parallel()
		released := make(chan string, 1)
		h := stubHook{
			release: func(dutID string) { released <- dutID },
		}
		c := NewController(h)
		t.Run("empty before adding", func(t *testing.T) {
			if got := c.ActiveDUTs(); len(got) != 0 {
				t.Errorf("ActiveDUTs() = %v; want empty", got)
			}
		})
		const d = "some-dut"
		c.AddDUT(d)
		t.Run("added DUT is present", func(t *testing.T) {
			want := []string{d}
			got := c.ActiveDUTs()
			if diff := cmp.Diff(want, got); diff != "" {
				t.Errorf("ActiveDUTs() mismatch (-want +got):\n%s", diff)
			}
		})
		t.Run("empty after draining", func(t *testing.T) {
			c.DrainDUT(d)
			c.Wait()
			if got := c.ActiveDUTs(); len(got) != 0 {
				t.Errorf("ActiveDUTs() = %v; want empty", got)
			}
		})
	})
	t.Run("draining missing DUT still releases", func(t *testing.T) {
		t.Parallel()
		released := make(chan string, 1)
		h := stubHook{
			release: func(dutID string) { released <- dutID },
		}
		c := NewController(h)

		const d = "some-dut"
		t.Run("drain", func(t *testing.T) {
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
		t.Run("terminate", func(t *testing.T) {
			c.TerminateDUT(d)
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
		assertDontHang(t, c.Wait, "Wait hanged")
	})
	t.Run("can terminate DUT even if starting errors", func(t *testing.T) {
		t.Parallel()
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				return nil, errors.New("some error")
			},
		}
		c := NewController(h)
		const d = "some-dut"
		c.AddDUT(d)
		c.TerminateDUT(d)
		assertDontHang(t, c.Wait, "Wait hanged")
	})
	t.Run("drain crashlooping bot still releases", func(t *testing.T) {
		t.Parallel()
		released := make(chan string, 1)
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				return nil, errors.New("some error")
			},
			release: func(dutID string) { released <- dutID },
		}
		c := NewController(h)
		const d = "some-dut"
		c.AddDUT(d)
		c.DrainDUT(d)
		c.Wait()
		select {
		case got := <-released:
			if got != d {
				t.Errorf("Got released bot %v; want %v", got, d)
			}
		case <-time.After(time.Second):
			t.Errorf("Did not release DUT")
		}
	})
	t.Run("terminate crashlooping bot still releases", func(t *testing.T) {
		t.Parallel()
		released := make(chan string, 1)
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				return nil, errors.New("some error")
			},
			release: func(dutID string) { released <- dutID },
		}
		c := NewController(h)
		const d = "some-dut"
		c.AddDUT(d)
		c.TerminateDUT(d)
		c.Wait()
		select {
		case got := <-released:
			if got != d {
				t.Errorf("Got released bot %v; want %v", got, d)
			}
		case <-time.After(time.Second):
			t.Errorf("Did not release DUT")
		}
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
		assertDontHang(t, c.DrainAll, "DrainAll hanged")
		c.Wait()
	})
	t.Run("terminate all does not hang", func(t *testing.T) {
		t.Parallel()
		c := NewController(stubHook{})
		c.AddDUT("ionasal")
		c.AddDUT("nero")
		assertDontHang(t, c.TerminateAll, "TerminateAll hanged")
		c.Wait()
	})
	t.Run("block DUTs stops add new DUT", func(t *testing.T) {
		t.Parallel()
		b := bot.NewFakeBot()
		var m sync.Mutex
		var started int
		h := stubHook{
			start: func(dutID string) (bot.Bot, error) {
				m.Lock()
				started++
				m.Unlock()
				return b, nil
			},
		}
		c := NewController(h)

		c.BlockDUTs()
		const d = "some-dut"
		c.AddDUT(d)
		m.Lock()
		got := started
		m.Unlock()
		if got != 0 {
			t.Errorf("Got %v bots started; want 0", got)
		}
	})
}

func assertDontHang(t *testing.T, f func(), msg string) {
	t.Helper()
	done := make(chan struct{})
	go func() {
		f()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatalf(msg)
	}
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
