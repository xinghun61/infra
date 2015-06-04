// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testclock

import (
	"time"

	"golang.org/x/net/context"
	"infra/libs/clock"
)

// UseTime instantiates a TestClock and returns a Context that is configured to
// use that clock, as well as the instantiated clock.
func UseTime(ctx context.Context, now time.Time) (rctx context.Context, tc TestClock) {
	tc = New(now)
	rctx = clock.Set(ctx, tc)
	return
}
