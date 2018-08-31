// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package annotations

import (
	"io"
)

// State stores the step state for writing annotations.
type State struct {
	w    io.Writer
	open bool
}

// NewState creates a new State.
func NewState(w io.Writer) *State {
	return &State{
		w: w,
	}
}

// OpenStep starts a new step.
func (s *State) OpenStep(name string) {
	SeedStep(s.w, name)
	StepCursor(s.w, name)
	StepStarted(s.w)
	s.open = true
}

// AddLink adds a link to the current step.
func (s *State) AddLink(label, url string) {
	StepLink(s.w, label, url)
}

// Close closes the current step, if any.
func (s *State) Close() {
	if s.open {
		StepClosed(s.w)
		s.open = false
	}
}
