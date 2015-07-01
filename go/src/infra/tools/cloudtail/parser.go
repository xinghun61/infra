// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"time"
)

// LogParser takes a line of text and extracts log related info from it.
type LogParser interface {
	// ParseLogLine returns log entry with all recognized info filled in or nil
	// if the line format is not recognized.
	ParseLogLine(line string) *Entry
}

// LogParserChain is a list of log parsers applied one after another until
// first hit.
type LogParserChain []LogParser

// ParseLogLine invokes all parsers in a chain until a first hit. If no parser
// recognizes a line, it returns Entry with unparsed text message as payload and
// default fields.
func (c LogParserChain) ParseLogLine(line string) *Entry {
	for _, p := range c {
		if entry := p.ParseLogLine(line); entry != nil {
			return entry
		}
	}
	return lineToEntry(line)
}

// StdParser returns a parser that recognizes common types of logs.
func StdParser() LogParser {
	// TODO(vadimsh): Recognize python logs, master logs, etc.
	return LogParserChain{}
}

// NullParser returns a parser that converts log line into a raw text Entry.
func NullParser() LogParser {
	return &nullParser{}
}

////////////////////////////////////////////////////////////////////////////////

type nullParser struct{}

func (p *nullParser) ParseLogLine(line string) *Entry { return lineToEntry(line) }

func lineToEntry(line string) *Entry {
	return &Entry{Timestamp: time.Now(), TextPayload: line}
}
