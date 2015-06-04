// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package clock

import (
	"time"
)

// A Timer implementation that uses time.Timer.
type systemTimer struct {
	T *time.Timer // The underlying timer. Starts as nil, is initialized on Reset.
}

var _ Timer = (*systemTimer)(nil)

func (t *systemTimer) GetC() (c <-chan time.Time) {
	if t.T != nil {
		c = t.T.C
	}
	return
}

func (t *systemTimer) Reset(d time.Duration) bool {
	if t.T == nil {
		t.T = time.NewTimer(d)
		return false
	}
	return t.T.Reset(d)
}

func (t *systemTimer) Stop() bool {
	if t.T == nil {
		return false
	}
	return t.T.Stop()
}
