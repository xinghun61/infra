// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"bufio"
	"io"

	"github.com/luci/luci-go/common/logging"
)

// PipeFromReader reads log lines from io.Reader, parses them and pushes to
// the buffer.
func PipeFromReader(src io.Reader, parser LogParser, buf PushBuffer, logger logging.Logger) error {
	scanner := bufio.NewScanner(src)
	source := make(chan string)
	go func() {
		defer close(source)
		for scanner.Scan() {
			source <- scanner.Text()
		}
	}()
	drainChannel(source, parser, buf, logger)
	return scanner.Err()
}
