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
				logger.Errorf("skipping line, unrecognized format: %s", line)
			}
			continue
		}
		if entry.InsertID == "" {
			insertID, err := computeInsertID(entry)
			if err != nil {
				if logger != nil {
					logger.Errorf("skipping line, can't compute insertId: %s", err)
				}
				continue
			}
			entry.InsertID = insertID
		}
		buf.Add(*entry)
	}
}

// computeInsertID takes a LogEntry and deterministically combines its fields
// to come up with an identifier used for log deduplication. Used only if parser
// doesn't implement something more smart or efficient.
func computeInsertID(e *Entry) (string, error) {
	hasher := sha1.New()
	hasher.Write([]byte(e.TextPayload))
	if e.StructPayload != nil {
		if err := json.NewEncoder(hasher).Encode(e.StructPayload); err != nil {
			return "", err
		}
	}
	ts := ""
	if !e.Timestamp.IsZero() {
		ts = fmt.Sprintf("%d", e.Timestamp.UnixNano())
	}
	return ts + ":" + base64.StdEncoding.EncodeToString(hasher.Sum(nil)[:12]), nil
}
