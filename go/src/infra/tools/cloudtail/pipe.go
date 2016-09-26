// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"bufio"
	"io"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"golang.org/x/net/context"
)

var (
	droppedCounter = metric.NewCounter("cloudtail/pipe_drops",
		"Log entries read from a pipe and dropped because the sender couldn't keep up",
		nil,
		field.String("log"),
		field.String("resource_type"),
		field.String("resource_id"))
)

// PipeFromReader reads log lines from io.Reader, parses them and pushes to
// the buffer.
func PipeFromReader(id ClientID, src io.Reader, parser LogParser, buf PushBuffer, ctx context.Context, lineBufferSize int) error {
	scanner := bufio.NewScanner(src)
	source := make(chan string, lineBufferSize)
	go func() {
		defer close(source)
		for scanner.Scan() {
			if lineBufferSize == 0 {
				source <- scanner.Text() // Blocking.
			} else {
				select {
				case source <- scanner.Text():
				default:
					// The buffer is full - drop this log line rather than blocking the pipe.
					droppedCounter.Add(ctx, 1, id.LogID, id.ResourceType, id.ResourceID)
				}
			}
		}
	}()
	drainChannel(source, parser, buf, logging.Get(ctx))
	return scanner.Err()
}
