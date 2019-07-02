// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package draining implements a draining state on contexts.
package draining

import (
	"context"
	"sync"
)

// key is a context value key.
type key struct{}

// value is a context value to store draining status.
type value struct {
	m sync.Mutex
	v bool
}

// WithDraining returns a context that can be marked as draining by
// calling the returned function.
func WithDraining(ctx context.Context) (context.Context, func()) {
	var dv value
	ctx = context.WithValue(ctx, key{}, &dv)
	return ctx, func() {
		dv.m.Lock()
		dv.v = true
		dv.m.Unlock()
	}
}

// IsDraining checks whether the context is marked draining.
func IsDraining(ctx context.Context) bool {
	dv, ok := ctx.Value(key{}).(*value)
	if !ok {
		return false
	}
	dv.m.Lock()
	v := dv.v
	dv.m.Unlock()
	return v
}
