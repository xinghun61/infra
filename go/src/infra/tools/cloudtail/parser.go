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

	// MergeLogLine appends the line of text to the existing Entry.  The Entry was
	// created by this LogParser.  Returns true if the merge succeeded, false if
	// the line should be added as a separate log entry.
	MergeLogLine(line string, e *Entry) bool
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

// MergeLogLine does nothing.  Concrete parsers should set the ParsedBy Entry
// member for their own MergeLogLine methods to be called.
func (c LogParserChain) MergeLogLine(line string, e *Entry) bool {
	return false
}

// StdParser returns a parser that recognizes common types of logs.
func StdParser() LogParser {
	return LogParserChain{
		&infraLogsParser{},
		&twistedLogsParser{},
		&puppetLogsParser{},
		&apacheErrorLogsParser{time.Local},
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
			ParsedBy:    p,
		}
	}
	return nil
}

func (p *infraLogsParser) MergeLogLine(line string, e *Entry) bool {
	e.TextPayload += "\n" + line
	return true
}

////////////////////////////////////////////////////////////////////////////////

var (
	twistedLogsRe = regexp.MustCompile(
		`(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[\+-]\d{4})` + // YYYY-MM-DD HH:MM:SS+ZZZZ
			` \[([^\]]+)\]` + // System
			` (.*)`) // Message
)

type twistedLogsParser struct{}

func (p *twistedLogsParser) ParseLogLine(line string) *Entry {
	if matches := twistedLogsRe.FindStringSubmatch(line); matches != nil {
		timestamp, err := time.Parse("2006-01-02 15:04:05-0700", matches[1])
		if err != nil {
			return nil
		}

		system := matches[2]
		message := matches[3]

		return &Entry{
			Timestamp:   timestamp,
			Severity:    Default,
			TextPayload: fmt.Sprintf("%s] %s", system, message),
			ParsedBy:    p,
		}
	}
	return nil
}

func (p *twistedLogsParser) MergeLogLine(line string, e *Entry) bool {
	e.TextPayload += "\n" + line
	return true
}

////////////////////////////////////////////////////////////////////////////////

var (
	puppetLogsRe = regexp.MustCompile(
		`(\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} [\+-]\d{4} \d{4})` + // Dow Mon DD HH:MM:SS +ZZZZ YYYY
			` (\w+)` + // Source
			` \((\w+)\)` + // Severity
			`: (.*)`) // Message

	// https://github.com/puppetlabs/puppet/blob/master/lib/puppet/util/log.rb
	puppetSeverities = map[string]Severity{
		"debug":   Debug,
		"info":    Info,
		"notice":  Notice,
		"warning": Warning,
		"err":     Error,
		"alert":   Alert,
		"emerg":   Emergency,
		"crit":    Critical,
	}
)

type puppetLogsParser struct{}

func (p *puppetLogsParser) ParseLogLine(line string) *Entry {
	if matches := puppetLogsRe.FindStringSubmatch(line); matches != nil {
		timestamp, err := time.Parse("Mon Jan 2 15:04:05 -0700 2006", matches[1])
		if err != nil {
			return nil
		}

		source := matches[2]
		severityText := matches[3]
		message := matches[4]

		severity, ok := puppetSeverities[severityText]
		if !ok {
			return nil
		}

		return &Entry{
			Timestamp:   timestamp,
			Severity:    severity,
			TextPayload: fmt.Sprintf("%s: %s", source, message),
			ParsedBy:    p,
		}
	}
	return nil
}

func (p *puppetLogsParser) MergeLogLine(line string, e *Entry) bool {
	e.TextPayload += "\n" + line
	return true
}

////////////////////////////////////////////////////////////////////////////////

var (
	apacheErrorLogsRe = regexp.MustCompile(
		`\[(\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4})\]` + // [Dow Mon DD HH:MM:SS YYYY]
			` \[(\w+)\]` + // Severity
			` \[client ([^\]]+)\]` + // Client
			` (.*)`) // Message

	// https://httpd.apache.org/docs/2.4/mod/core.html#loglevel
	apacheErrorLogSeverities = map[string]Severity{
		"emerg":  Emergency,
		"alert":  Alert,
		"crit":   Critical,
		"error":  Error,
		"warn":   Warning,
		"notice": Notice,
		"info":   Info,
		"debug":  Debug,
	}
)

type apacheErrorLogsParser struct {
	localTimeZone *time.Location
}

func (p *apacheErrorLogsParser) ParseLogLine(line string) *Entry {
	if matches := apacheErrorLogsRe.FindStringSubmatch(line); matches != nil {
		timestamp, err := time.ParseInLocation("Mon Jan 2 15:04:05 2006", matches[1], p.localTimeZone)
		if err != nil {
			return nil
		}

		severityText := matches[2]
		client := matches[3]
		message := matches[4]

		severity, ok := apacheErrorLogSeverities[severityText]
		if !ok {
			return nil
		}

		return &Entry{
			Timestamp:   timestamp,
			Severity:    severity,
			TextPayload: fmt.Sprintf("[%s] %s", client, message),
			ParsedBy:    p,
		}
	}
	return nil
}

func (p *apacheErrorLogsParser) MergeLogLine(line string, e *Entry) bool {
	e.TextPayload += "\n" + line
	return true
}

////////////////////////////////////////////////////////////////////////////////

type nullParser struct{}

func (p *nullParser) ParseLogLine(line string) *Entry { return lineToEntry(line) }

func (p *nullParser) MergeLogLine(line string, e *Entry) bool {
	e.TextPayload += "\n" + line
	return true
}

func lineToEntry(line string) *Entry {
	return &Entry{Timestamp: time.Now(), TextPayload: line}
}
