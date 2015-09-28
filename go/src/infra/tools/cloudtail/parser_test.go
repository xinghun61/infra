// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"reflect"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestLogParserChain(t *testing.T) {
	Convey("StdParser coverage", t, func() {
		So(StdParser(), ShouldNotBeNil)
	})

	Convey("Empty works", t, func() {
		chain := LogParserChain{}
		entry := chain.ParseLogLine("hi")
		So(entry, ShouldNotBeNil)
		So(entry.TextPayload, ShouldEqual, "hi")
	})

	Convey("Non empty works", t, func() {
		parser1 := &callbackParser{
			cb: func(string) *Entry { return nil },
		}
		parser2 := &callbackParser{
			cb: func(line string) *Entry { return &Entry{TextPayload: line + ", yo"} },
		}
		chain := LogParserChain{parser1, parser2}
		entry := chain.ParseLogLine("hi")
		So(entry.TextPayload, ShouldEqual, "hi, yo")
	})
}

func TestInfraLogsParser(t *testing.T) {
	tests := []struct {
		line          string
		wantSuccess   bool
		wantTimestamp string
		wantSeverity  Severity
		wantPayload   infraLogsEntry
	}{
		{
			line:        "not a valid log line",
			wantSuccess: false,
		},
		{
			line:          "[I2015-09-22T01:02:03.000004+00:00 123 456 __main__:789] Hello world",
			wantSuccess:   true,
			wantTimestamp: "2015-09-22T01:02:03.000004+00:00",
			wantSeverity:  Info,
			wantPayload: infraLogsEntry{
				ProcessID: 123,
				ThreadID:  456,
				Module:    "__main__",
				Line:      789,
				Message:   "Hello world",
			},
		},
		{
			line:          "[C2015-09-22T01:02:03.000004-07:00 123 456 foo.bar:789] Hello world",
			wantSuccess:   true,
			wantTimestamp: "2015-09-22T01:02:03.000004-07:00",
			wantSeverity:  Critical,
			wantPayload: infraLogsEntry{
				ProcessID: 123,
				ThreadID:  456,
				Module:    "foo.bar",
				Line:      789,
				Message:   "Hello world",
			},
		},
		{
			line:          "[C2015-09-22T01:02:03.000004-07:00 123 -456 foo.bar:789] Hello world",
			wantSuccess:   true,
			wantTimestamp: "2015-09-22T01:02:03.000004-07:00",
			wantSeverity:  Critical,
			wantPayload: infraLogsEntry{
				ProcessID: 123,
				ThreadID:  -456,
				Module:    "foo.bar",
				Line:      789,
				Message:   "Hello world",
			},
		},
	}

	timeLayout := "2006-01-02T15:04:05.000000-07:00"

	p := infraLogsParser{}
	for i, test := range tests {
		got := p.ParseLogLine(test.line)
		if test.wantSuccess && got == nil {
			t.Errorf("%d: ParseLogLine('%s') -> nil, want success", i, test.line)
		} else if !test.wantSuccess && got != nil {
			t.Errorf("%d: ParseLogLine('%s') -> %v, want failure", i, test.line, got)
		} else if test.wantSuccess && got.Timestamp.Format(timeLayout) != test.wantTimestamp {
			t.Errorf("%d: ParseLogLine('%s').Timestamp -> %v, want %v", i, test.line, got.Timestamp, test.wantTimestamp)
		} else if test.wantSuccess && got.Severity != test.wantSeverity {
			t.Errorf("%d: ParseLogLine('%s').Severity -> %v, want %v", i, test.line, got.Severity, test.wantSeverity)
		} else if test.wantSuccess && !reflect.DeepEqual(*got.StructPayload.(*infraLogsEntry), test.wantPayload) {
			t.Errorf("%d: ParseLogLine('%s').StructPayload -> %v, want %v", i, test.line, *got.StructPayload.(*infraLogsEntry), test.wantPayload)
		}
	}
}

type callbackParser struct {
	cb func(line string) *Entry
}

func (p *callbackParser) ParseLogLine(line string) *Entry { return p.cb(line) }
