// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package clock

import (
	"time"
)

// A Clock is an interface to system time.
//
// The standard clock is SystemClock, which falls through to the system time
// library. Another clock, FakeClock, is available to simulate time facilities
// for testing.
type Clock interface {
	Now() time.Time                       // Returns the current time (see time.Now).
	Sleep(time.Duration)                  // Sleeps the current goroutine (see time.Sleep)
	NewTimer() Timer                      // Creates a new Timer instance.
	After(time.Duration) <-chan time.Time // Waits a duration, then sends the current time.
}
