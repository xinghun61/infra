// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"fmt"
	"regexp"
	"strconv"
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
	return LogParserChain{
		&infraLogsParser{},
	}
}

// NullParser returns a parser that converts log line into a raw text Entry.
func NullParser() LogParser {
	return &nullParser{}
}

////////////////////////////////////////////////////////////////////////////////

var (
	infraLogsRe = regexp.MustCompile(
		`^\[` +
			`([DIWEC])` + // Severity
			`(\d{4}-\d{2}-\d{2}` + // YYYY-MM-DD
			`T\d{2}:\d{2}:\d{2}` + // THH:MM:SS
			`(?:\.\d{6})?` + // Optional milliseconds
			`(?:[\+-]\d{2}:\d{2})?` + // Optional timezone offset
			`)` +
			` (\d+)` + // PID
			` (-?\d+)` + // TID
			` ([^:]+):(\d+)` + // Module and line number
			`\] (.*)`) // Message

	infraLogsSeverity = map[string]Severity{
		"D": Debug,
		"I": Info,
		"W": Warning,
		"E": Error,
		"C": Critical,
	}
)

type infraLogsEntry struct {
	ProcessID int    `json:"processId"`
	ThreadID  int    `json:"threadId"`
	Module    string `json:"module"`
	Line      int    `json:"line"`
	Message   string `json:"message"`
}

type infraLogsParser struct{}

func (p *infraLogsParser) ParseLogLine(line string) *Entry {
	if matches := infraLogsRe.FindStringSubmatch(line); matches != nil {
		timestamp, err := time.Parse("2006-01-02T15:04:05.000000-07:00", matches[2])
		if err != nil {
			return nil
		}

		severity := matches[1]
		processID, _ := strconv.Atoi(matches[3])
		module := matches[5]
		line, _ := strconv.Atoi(matches[6])
		message := matches[7]

		return &Entry{
			Timestamp:   timestamp,
			Severity:    infraLogsSeverity[severity],
			TextPayload: fmt.Sprintf("%d %s:%d] %s", processID, module, line, message),
		}
	}
	return nil
}

////////////////////////////////////////////////////////////////////////////////

type nullParser struct{}

func (p *nullParser) ParseLogLine(line string) *Entry { return lineToEntry(line) }

func lineToEntry(line string) *Entry {
	return &Entry{Timestamp: time.Now(), TextPayload: line}
}
