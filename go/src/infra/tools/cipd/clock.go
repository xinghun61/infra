// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import "time"

// clock is a global mockable clock instance.
var clock clockInterface = &realClock{}

type clockInterface interface {
	Now() time.Time
	Sleep(time.Duration)
}

type realClock struct{}

func (c *realClock) Now() time.Time        { return time.Now() }
func (c *realClock) Sleep(d time.Duration) { time.Sleep(d) }
