// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package clock

import (
	"time"
)

// Timer is a wrapper around the time.Timer structure.
type Timer interface {
	GetC() <-chan time.Time     // Returns the underlying timer's channel, or nil if not configured.
	Reset(d time.Duration) bool // See time.Timer.
	Stop() bool                 // See time.Timer.
}
