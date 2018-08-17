// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package compilerproxylog

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"strings"
	"time"
	"unicode"
)

const (
	createdLayout   = "2006/01/02 15:04:05"
	timestampLayout = "0102 15:04:05.000000"
)

var (
	createdPrefix        = []byte("Log file created at: ")
	runningMachinePrefix = []byte("Running on machine: ")
	loglineFormatPrefix  = []byte("Log line format: ")
)

// LogLevel is glog logging level.
type LogLevel int

const (
	contLine LogLevel = iota
	// Info is INFO level.
	Info
	// Warning is WARNING level.
	Warning
	// Error is ERROR level.
	Error
	// Fatal is FATAL level.
	Fatal
)

func logLevel(b []byte) (LogLevel, error) {
	if len(b) == 0 {
		return contLine, fmt.Errorf("empty loglevel")
	}
	switch b[0] {
	case 'I':
		return Info, nil
	case 'W':
		return Warning, nil
	case 'E':
		return Error, nil
	case 'F':
		return Fatal, nil
	}
	return contLine, nil
}

func (lv LogLevel) String() string {
	switch lv {
	case Info:
		return "INFO"
	case Warning:
		return "WARNING"
	case Error:
		return "ERROR"
	case Fatal:
		return "FATAL"
	}
	return ""
}

func logTimestamp(dt []byte) (time.Time, error) {
	return time.Parse(timestampLayout, string(dt))
}

// Logline is one logical log line.
type Logline struct {
	// Level is logging level.
	Level LogLevel
	// Timestamp is time of log.
	Timestamp time.Time
	// ThreadID is thread id.
	ThreadID string
	// Lines is log text lines. len(Lines) >= 1.
	Lines []string
}

func isSpace(ch rune) bool {
	return ch == ' '
}

// ParseLogline parses one line as Logline.
func ParseLogline(line []byte) (Logline, error) {
	// Parse log line that matches with `^([IWEF])(\d{4} \d{2}:\d{2}:\d{2}.\d{6}) *(\d+) *(.*)`.

	if len(line) < len("I")+len(timestampLayout)+1 {
		return Logline{Lines: []string{string(line)}}, nil
	}

	if !strings.Contains("IWEF", string(line[:1])) {
		return Logline{Lines: []string{string(line)}}, nil
	}

	lv, err := logLevel(line[:1])
	if err != nil {
		return Logline{Lines: []string{string(line)}}, nil
	}

	t, err := logTimestamp(line[1 : 1+len(timestampLayout)])
	if err != nil {
		return Logline{Lines: []string{string(line)}}, nil
	}

	// Parse restline as `(\d+) *(.*)`
	restline := strings.TrimLeftFunc(string(line[1+len(timestampLayout):]), isSpace)
	afterThreadID := strings.TrimLeftFunc(restline, unicode.IsDigit)
	if afterThreadID == restline {
		// Not match with `(\d+)'.
		return Logline{Lines: []string{string(line)}}, nil
	}

	threadID := restline[:len(restline)-len(afterThreadID)]

	return Logline{
		Level:     lv,
		Timestamp: t,
		ThreadID:  threadID,
		Lines:     []string{strings.TrimLeftFunc(afterThreadID, isSpace)},
	}, nil
}

// GlogParser is a parser of glog.
type GlogParser struct {
	scanner *bufio.Scanner
	// Created is a timestamp when the log file is created.
	Created time.Time
	// Machine is a machine name where the log file is created.
	Machine string

	cur  Logline
	next Logline
	err  error
}

// NewGlogParser creates new GlogParser on rd.
func NewGlogParser(rd io.Reader) (*GlogParser, error) {
	gp := &GlogParser{
		scanner: bufio.NewScanner(rd),
	}
	for gp.scanner.Scan() {
		line := gp.scanner.Bytes()
		if bytes.HasPrefix(line, createdPrefix) {
			var err error
			gp.Created, err = time.Parse(createdLayout, string(line[len(createdPrefix):]))
			if err != nil {
				return nil, err
			}
			continue
		}
		if bytes.HasPrefix(line, runningMachinePrefix) {
			gp.Machine = string(line[len(runningMachinePrefix):])
			continue
		}
		if bytes.HasPrefix(line, loglineFormatPrefix) {
			return gp, nil
		}
	}
	if err := gp.scanner.Err(); err != nil {
		return nil, err
	}
	return nil, fmt.Errorf("not glog file?")
}

// Next scans next Logline. return true if Logline exists.
func (gp *GlogParser) Next() bool {
	gp.cur = gp.next
	gp.next = Logline{}
	for gp.scanner.Scan() {
		line, err := ParseLogline(gp.scanner.Bytes())
		if err != nil {
			gp.err = err
			return false
		}
		if line.Timestamp.Year() == 0 {
			line.Timestamp = line.Timestamp.AddDate(gp.Created.Year(), 0, 0)
		}
		if gp.cur.Level == contLine {
			gp.cur = line
			continue
		}
		if line.Level == contLine {
			gp.cur.Lines = append(gp.cur.Lines, line.Lines...)
			continue
		}
		gp.next = line
		return true
	}
	return gp.cur.Level != contLine
}

// Err returns last error.
func (gp *GlogParser) Err() error {
	return gp.err
}

// Logline returns last Logline parsed by Next().
func (gp *GlogParser) Logline() Logline {
	return gp.cur
}
