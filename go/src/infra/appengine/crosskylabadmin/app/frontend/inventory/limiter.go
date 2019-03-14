// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"sync"
	"time"
)

// rateLimiter is a simple rate limiter.
type rateLimiter struct {
	mutex sync.Mutex
	// limitPerPeriod is the max count allowed per period.  If
	// zero or negative, rate limiting is disabled.
	limitPerPeriod int
	period         time.Duration
	count          int
	lastPeriod     time.Time
}

// TryRequest asks to try a request.  If the request isn't rate
// limited, return true and count the request internally.  This method
// is concurrent safe.
func (r *rateLimiter) TryRequest() bool {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	if r.limitPerPeriod <= 0 {
		return true
	}
	r.updatePeriod()
	if r.count >= r.limitPerPeriod {
		return false
	}
	r.count++
	return true
}

func (r *rateLimiter) updatePeriod() {
	newPeriod := r.lastPeriod.Add(r.period)
	now := time.Now()
	if !now.After(newPeriod) {
		return
	}
	r.lastPeriod = now
	r.count = 0
}
