// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logutils

import (
	"time"

	"go.chromium.org/luci/common/logging"
)

// NewThrottledInfoLogger returns a logger that logs messages at info level no
// more than once every delay interval.
func NewThrottledInfoLogger(logger logging.Logger, delay time.Duration) *ThrottledInfoLogger {
	return &ThrottledInfoLogger{
		logger: logger,
		delay:  delay,
	}
}

// ThrottledInfoLogger logs messages at info level throttled to some frequency.
type ThrottledInfoLogger struct {
	logger       logging.Logger
	delay        time.Duration
	latestOutput time.Time
}

// MaybeLog logs the given message if the last message successfully logged is
// older than a prespecified delay.
func (t *ThrottledInfoLogger) MaybeLog(message string) {
	if t.shouldLog() {
		t.logger.Infof("%s", message)
		t.reportLogged()
	}
}

func (t *ThrottledInfoLogger) shouldLog() bool {
	return t.logger != nil && time.Now().After(t.latestOutput.Add(t.delay))
}

func (t *ThrottledInfoLogger) reportLogged() {
	t.latestOutput = time.Now()
}
