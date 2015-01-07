// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

// No tests in this file, just a mockClock function used from other tests.

import (
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

type mockedClocked struct {
	now time.Time
}

func (c *mockedClocked) Now() time.Time        { return c.now }
func (c *mockedClocked) Sleep(d time.Duration) { c.now = c.now.Add(d) }

func mockClock(now time.Time) {
	prev := clock
	clock = &mockedClocked{now: now}
	Reset(func() { clock = prev })
}
