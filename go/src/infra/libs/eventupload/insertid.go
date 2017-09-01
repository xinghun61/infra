// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package eventupload is a library for streaming events to BigQuery.
package eventupload

import (
	"fmt"
	"os"
	"sync/atomic"
	"time"
)

var (
	// These global value is used to populate a zero-value
	// InsertIDGenerator.
	defaultPrefix      string
	defaultPrefixError error
)

func init() {
	h, err := os.Hostname()
	if err != nil {
		h = "UNKNOWN"
		defaultPrefixError = err
	}
	t := time.Now().UnixNano()
	defaultPrefix = fmt.Sprintf("%s:%d:%d", h, os.Getpid(), t)
}

// InsertIDGenerator generates unique Insert IDs.
//
// BigQuery uses Insert IDs to deduplicate rows in the streaming insert buffer.
// The association between Insert ID and row persists only for the time the row
// is in the buffer.
//
// InsertIDGenerator is safe for concurrent use.
type InsertIDGenerator struct {
	// Counter is an atomically-managed counter used to differentiate Insert
	// IDs produced by the same process.
	Counter int64
	// Prefix should be able to uniquely identify this specific process,
	// to differentiate Insert IDs produced by different processes.
	//
	// If empty, prefix will be derived from system and process specific
	// properties.
	Prefix string
}

// Generate returns a unique Insert ID.
func (id *InsertIDGenerator) Generate() (string, error) {
	var err error
	prefix := id.Prefix
	if prefix == "" {
		if defaultPrefixError != nil {
			return "", defaultPrefixError
		}
		prefix = defaultPrefix
	}
	c := atomic.AddInt64(&id.Counter, 1)
	return fmt.Sprintf("%s:%d", prefix, c), err
}
