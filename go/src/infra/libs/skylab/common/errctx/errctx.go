// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Package errctx provides implementations of context.Context that allow for
// cancellation or deadline expiration with custom error messages.
package errctx

import (
	"context"
	"sync"
	"time"
)

// cancelContext is an implementation of context.Context, in which the context
// can be cancelled with a custom error.
type cancelContext struct {
	parent context.Context

	cancelOnce sync.Once
	errMutex   sync.RWMutex
	done       chan struct{}
	err        error
}

// Deadline implements context.Context.
func (c *cancelContext) Deadline() (time.Time, bool) {
	return c.parent.Deadline()
}

// Done implements context.Context.
func (c *cancelContext) Done() <-chan struct{} {
	return c.done
}

// Err implements context.Context.
func (c *cancelContext) Err() error {
	c.errMutex.RLock()
	e := c.err
	c.errMutex.RUnlock()
	return e
}

// Value implements context.Context.
func (c *cancelContext) Value(key interface{}) interface{} {
	return c.parent.Value(key)
}

// cancel cancels the context with the given error.
//
// If no error is provided, context.Canceled is inferred.
func (c *cancelContext) cancel(err error) {
	c.cancelOnce.Do(func() {
		c.errMutex.Lock()
		if err == nil {
			c.err = context.Canceled
		} else {
			c.err = err
		}
		close(c.done)
		c.errMutex.Unlock()
	})
}

// propagate launches a goroutine that propagates context cancellation from
// parent context.
func (c *cancelContext) propagate() {
	go func() {
		select {
		case <-c.parent.Done():
			c.cancel(c.parent.Err())
		case <-c.Done():
		}
	}()
}

func newCancelContext(parent context.Context) *cancelContext {
	c := &cancelContext{
		parent: parent,
		done:   make(chan struct{}),
	}
	c.propagate()
	return c
}

// WithCancel returns a child context with a cancellation function that accepts
// custom errors.
func WithCancel(parent context.Context) (context.Context, func(error)) {
	c := newCancelContext(parent)
	return c, c.cancel
}
