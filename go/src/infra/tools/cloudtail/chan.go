// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
)

// drainChannel reads log lines from the channel and pushes them to the buffer.
//
// It reads non-empty log lines from a channel (until it is closed), extracts
// logging metadata from them (severity, timestamp, etc) via the given parser
// and pushes log entries to the push buffer.
//
// Doesn't return errors: use buf.Stop() to check for any errors during sending.
func drainChannel(ctx context.Context, src chan string, parser LogParser, buf PushBuffer) {
	// Helper function to parse log line into an Entry.
	parseEntry := func(line string) *Entry {
		line = strings.TrimSpace(line)
		if line == "" {
			return nil
		}
		entry := parser.ParseLogLine(line)
		if entry == nil {
			logging.Errorf(ctx, "skipping line, unrecognized format: %s", line)
			return nil
		}
		if entry.InsertID == "" {
			insertID, err := computeInsertID(entry)
			if err != nil {
				logging.WithError(err).Errorf(ctx, "skipping line, can't compute insertId")
				return nil
			}
			entry.InsertID = insertID
		}
		return entry
	}

	line := ""
	alive := true

	// Note: ignore ctx.Done() here, since we don't want to block the pipeline
	// when context is canceled. Instead we'll run the loop as usual and send the
	// entries to buf.Send() which would just drop them. That way we don't block
	// the producer and let it finish what it's doing.
	for {
		line, alive = <-src
		if !alive {
			break
		}
		if entry := parseEntry(line); entry != nil {
			buf.Send(ctx, *entry)
		}
	}
}

// computeInsertID takes a LogEntry and deterministically combines its fields
// to come up with an identifier used for log deduplication. Used only if parser
// doesn't implement something more smart or efficient.
func computeInsertID(e *Entry) (string, error) {
	hasher := sha1.New()
	hasher.Write([]byte(e.TextPayload))
	if e.JSONPayload != nil {
		if err := json.NewEncoder(hasher).Encode(e.JSONPayload); err != nil {
			return "", err
		}
	}
	ts := ""
	if !e.Timestamp.IsZero() {
		ts = fmt.Sprintf("%d", e.Timestamp.UnixNano())
	}
	return ts + ":" + base64.StdEncoding.EncodeToString(hasher.Sum(nil)[:12]), nil
}
