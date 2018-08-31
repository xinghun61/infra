// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package annotee implements a Go interface for writing annotation
// lines that annotee can parse and turn into LogDog annotations.
//
// See the basic package for the low level interface.
package annotee

import (
	"io"

	"infra/cmd/skylab_swarming_worker/internal/annotee/basic"
)

// Client manages annotation writing.
type Client struct {
	w    io.Writer
	open bool
}

// NewClient creates a new Client.
func NewClient(w io.Writer) *Client {
	return &Client{
		w: w,
	}
}

// OpenStep starts a new step.
func (c *Client) OpenStep(name string) {
	c.Close()
	basic.SeedStep(c.w, name)
	basic.StepCursor(c.w, name)
	basic.StepStarted(c.w)
	c.open = true
}

// AddLink adds a link to the current step.
func (c *Client) AddLink(label, url string) {
	basic.StepLink(c.w, label, url)
}

// Close closes the current step, if any.
func (c *Client) Close() {
	if c.open {
		basic.StepClosed(c.w)
		c.open = false
	}
}
