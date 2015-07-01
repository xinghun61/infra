// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"strings"

	"github.com/luci/luci-go/common/logging"
)

// drainChannel reads non-empty log lines from a channel (until it is closed),
// extracts logging metadata from them (severity, timestamp, etc) via given
// parser and pushes log entries to the push buffer. Doesn't return errors: use
// buf.Stop() to check for any errors during sending.
func drainChannel(src chan string, parser LogParser, buf PushBuffer, logger logging.Logger) {
	for line := range src {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		entry := parser.ParseLogLine(line)
		if entry == nil {
			if logger != nil {
				logger.Warningf("skipping line, unrecognized format: %s", line)
			}
			continue
		}
		buf.Add(*entry)
	}
}
