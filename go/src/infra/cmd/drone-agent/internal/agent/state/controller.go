// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state

import (
	"sync"

	"infra/cmd/drone-agent/internal/bot"
)

// ControllerHook defines the interface that a Controller uses to
// interact with the external world.
type ControllerHook interface {
	// StartBot starts a bot process for the DUT.
	StartBot(dutID string) (bot.Bot, error)
	// ReleaseDUT is called to release the DUT for a bot process
	// that has finished.
	ReleaseDUT(dutID string)
}

// Controller provides running bots for DUTs.  Callers tell Controller
// what DUTs to add, drain, or terminate, and Controller makes sure
// there are bots running or not running for those DUTs.
type Controller struct {
	hook ControllerHook
	wg   sync.WaitGroup

	// The following fields are covered by the mutex.
	m    sync.Mutex
	duts map[string]dutSignals
}

// NewController creates a new Controller.
func NewController(h ControllerHook) *Controller {
	c := &Controller{
		hook: h,
		duts: make(map[string]dutSignals),
	}
	return c
}

// AddDUT adds a DUT to have bots running for it.  If the DUT was
// already added, do nothing.  This method is concurrency safe.
func (c *Controller) AddDUT(dutID string) {
	c.m.Lock()
	defer c.m.Unlock()
	if _, ok := c.duts[dutID]; ok {
		// DUT already has bot running.
		return
	}
	s := newDUTSignals()
	c.duts[dutID] = s
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		runBotForDUT(c.hook, dutID, s)
		c.m.Lock()
		delete(c.duts, dutID)
		c.m.Unlock()
	}()
}

// runBotForDUT keeps a Swarming bot running for the DUT.  Signals to
// drain or terminate should be sent to the channel.  This function
// otherwise runs forever.
func runBotForDUT(h ControllerHook, dutID string, s dutSignals) {
	for {
		select {
		case <-s.drain:
			return
		case <-s.terminate:
			return
		default:
		}
		b, err := h.StartBot(dutID)
		if err != nil {
			// TODO(ayatane): Log error?
			continue
		}
		wait := make(chan struct{})
		go func() {
			_ = b.Wait()
			close(wait)
		}()
		var stop bool
	listenForSignals:
		for {
			select {
			case <-s.drain:
				// TODO(ayatane): Log error?
				_ = b.Drain()
				stop = true
			case <-s.terminate:
				// TODO(ayatane): Log error?
				_ = b.Terminate()
				stop = true
			case <-wait:
				break listenForSignals
			}
		}
		if stop {
			h.ReleaseDUT(dutID)
			return
		}
	}
}

// DrainDUT removes a DUT to no longer have bots running for it and
// drains its current bot.  This method can be called repeatedly.
// This method is concurrency safe.
func (c *Controller) DrainDUT(dutID string) {
	c.m.Lock()
	s, ok := c.duts[dutID]
	c.m.Unlock()
	if ok {
		s.sendDrain()
	}
}

// TerminateDUT removes a DUT to no longer have bots running for it
// and terminates its current bot.  This method can be called
// repeatedly.  This method is concurrency safe.
func (c *Controller) TerminateDUT(dutID string) {
	c.m.Lock()
	s, ok := c.duts[dutID]
	c.m.Unlock()
	if ok {
		s.sendTerminate()
	}
}

// DrainAll drains all DUTs.  This method is concurrency safe, but
// beware calling AddDUT concurrently with this.
func (c *Controller) DrainAll() {
	c.m.Lock()
	for _, s := range c.duts {
		s.sendDrain()
	}
	c.m.Unlock()
}

// TerminateAll terminates all DUTs.  This method is concurrency safe,
// but beware calling AddDUT concurrently with this.
func (c *Controller) TerminateAll() {
	c.m.Lock()
	for _, s := range c.duts {
		s.sendTerminate()
	}
	c.m.Unlock()
}

// Wait for all Swarming bots to finish.  It is the caller's
// responsibility to make sure all bots are terminated or drained,
// else this call will hang.
func (c *Controller) Wait() {
	c.wg.Wait()
}

type dutSignals struct {
	drain     chan struct{}
	terminate chan struct{}
}

func newDUTSignals() dutSignals {
	return dutSignals{
		drain:     make(chan struct{}, 1),
		terminate: make(chan struct{}, 1),
	}
}

func (s dutSignals) sendDrain() {
	select {
	case s.drain <- struct{}{}:
	default:
	}
}

func (s dutSignals) sendTerminate() {
	select {
	case s.terminate <- struct{}{}:
	default:
	}
}
