// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package state implements the agent state.  This is a separate
// package to enforce access to a limited public API.
package state

import (
	"context"
	"time"

	"infra/cmd/drone-agent/internal/delay"
)

// State contains the agent state for the lifetime of one drone UUID
// assignment.
type State struct {
	uuid string
	*Controller
	expireTimer *delay.Timer
}

// New creates a new instance of agent state.
func New(uuid string, h ControllerHook) *State {
	return &State{
		uuid:       uuid,
		Controller: NewController(h),
	}
}

// UUID returns the drone UUID.
func (s *State) UUID() string {
	return s.uuid
}

// GraceInterval is the amount of time to provide for bots to
// terminate gracefully.
const GraceInterval = 3 * time.Minute

// WithExpire sets up the delayable expiration context.
func (s *State) WithExpire(ctx context.Context, t time.Time) context.Context {
	t = t.Add(-GraceInterval)
	ctx, s.expireTimer = delay.WithTimer(ctx, t)
	return ctx
}

// SetExpiration sets a new expiration time.  Note that if the
// expiration already fired, this does nothing.
func (s *State) SetExpiration(t time.Time) {
	s.expireTimer.Set(t)
}
