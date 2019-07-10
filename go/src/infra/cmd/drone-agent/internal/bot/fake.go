// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package bot

import "sync"

// FakeBot is a fake implementation of Bot for tests.
type FakeBot struct {
	m       sync.Mutex
	stopped bool
	done    chan error

	// DrainFunc, if set, is called when the bot is drained.  The
	// default behavior is Stop.
	DrainFunc func(*FakeBot) error
	// TerminateFunc, if set, is called when the bot is terminated.
	// The default behavior is Stop.
	TerminateFunc func(*FakeBot) error
}

// NewFakeBot returns a new FakeBot.
func NewFakeBot() *FakeBot {
	return &FakeBot{
		done: make(chan error, 1),
	}
}

// Wait implements Bot.
func (b *FakeBot) Wait() error {
	return <-b.done
}

// Drain implements Bot.
func (b *FakeBot) Drain() error {
	if f := b.DrainFunc; f != nil {
		return f(b)
	}
	b.Stop()
	return nil
}

// Terminate implements Bot.
func (b *FakeBot) Terminate() error {
	if f := b.TerminateFunc; f != nil {
		return f(b)
	}
	b.Stop()
	return nil
}

// Stop stops the "bot process".
func (b *FakeBot) Stop() {
	b.StopWith(nil)
}

// StopWith stops the "bot process" with an error to be returned from Wait.
func (b *FakeBot) StopWith(err error) {
	b.m.Lock()
	defer b.m.Unlock()
	if b.stopped {
		return
	}
	b.stopped = true
	b.done <- err
	close(b.done)
}
