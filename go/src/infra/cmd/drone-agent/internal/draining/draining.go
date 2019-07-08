// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package draining implements a draining state on contexts.
package draining

import (
	"context"
)

// key is a context value key.
type key struct{}

// value is a context value to store draining status.
type value struct {
	c chan struct{}
}

// WithDraining returns a context that can be marked as draining by
// calling the returned function.
func WithDraining(ctx context.Context) (context.Context, func()) {
	dv := value{
		c: make(chan struct{}),
	}
	ctx = context.WithValue(ctx, key{}, &dv)
	return ctx, func() {
		close(dv.c)
	}
}

// IsDraining checks whether the context is draining.  If the context
// is not set up for draining, return false.
func IsDraining(ctx context.Context) bool {
	select {
	case <-C(ctx):
		return true
	default:
		return false
	}
}

// C returns a channel associated with the draining context.  The
// channel is closed when the context is draining.  If the context is
// not set up for draining, return nil (nil channels block forever on
// receive).
func C(ctx context.Context) <-chan struct{} {
	dv, ok := ctx.Value(key{}).(*value)
	if !ok {
		return nil
	}
	return dv.c
}
