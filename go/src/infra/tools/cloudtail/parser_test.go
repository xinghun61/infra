// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
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

type textTestCase struct {
	line          string
	wantSuccess   bool
	wantTimestamp string
	wantSeverity  Severity
	wantPayload   string
}

func testTextLogsParser(t *testing.T, p LogParser, cases []textTestCase) {
	timeLayout := "2006-01-02T15:04:05.000000-07:00"

	for i, test := range cases {
		got := p.ParseLogLine(test.line)
		if test.wantSuccess && got == nil {
			t.Errorf("%d: ParseLogLine('%s') -> nil, want success", i, test.line)
		} else if !test.wantSuccess && got != nil {
			t.Errorf("%d: ParseLogLine('%s') -> %v, want failure", i, test.line, got)
		} else if test.wantSuccess && got.Timestamp.Format(timeLayout) != test.wantTimestamp {
			t.Errorf("%d: ParseLogLine('%s').Timestamp -> %v, want %v", i, test.line, got.Timestamp, test.wantTimestamp)
		} else if test.wantSuccess && got.Severity != test.wantSeverity {
			t.Errorf("%d: ParseLogLine('%s').Severity -> %v, want %v", i, test.line, got.Severity, test.wantSeverity)
		} else if test.wantSuccess && got.TextPayload != test.wantPayload {
			t.Errorf("%d: ParseLogLine('%s').TextPayload -> %v, want %v", i, test.line, got.TextPayload, test.wantPayload)
		}
	}
}

func TestInfraLogsParser(t *testing.T) {
	testTextLogsParser(t, &infraLogsParser{},
		[]textTestCase{
			{
				line:        "not a valid log line",
				wantSuccess: false,
			},
			{
				line:          "[I2015-09-22T01:02:03.000004+00:00 123 456 __main__:789] Hello world",
				wantSuccess:   true,
				wantTimestamp: "2015-09-22T01:02:03.000004+00:00",
				wantSeverity:  Info,
				wantPayload:   "123 __main__:789] Hello world",
			},
			{
				line:          "[C2015-09-22T01:02:03.000004-07:00 123 456 foo.bar:789] Hello world",
				wantSuccess:   true,
				wantTimestamp: "2015-09-22T01:02:03.000004-07:00",
				wantSeverity:  Critical,
				wantPayload:   "123 foo.bar:789] Hello world",
			},
			{
				line:          "[C2015-09-22T01:02:03.000004-07:00 123 -456 foo.bar:789] Hello world",
				wantSuccess:   true,
				wantTimestamp: "2015-09-22T01:02:03.000004-07:00",
				wantSeverity:  Critical,
				wantPayload:   "123 foo.bar:789] Hello world",
			},
		})
}

func TestTwistedLogsParser(t *testing.T) {
	testTextLogsParser(t, &twistedLogsParser{},
		[]textTestCase{
			{
				line:        "not a valid log line",
				wantSuccess: false,
			},
			{
				line:          "2015-09-27 23:40:38-0700 [-] Finished processing request with id: 97038920",
				wantSuccess:   true,
				wantTimestamp: "2015-09-27T23:40:38.000000-07:00",
				wantSeverity:  Default,
				wantPayload:   "-] Finished processing request with id: 97038920",
			},
			{
				line:          "2015-09-27 23:41:00+0000 [HTTP11ClientProtocol,client] GitilesPoller: No new commits.",
				wantSuccess:   true,
				wantTimestamp: "2015-09-27T23:41:00.000000+00:00",
				wantSeverity:  Default,
				wantPayload:   "HTTP11ClientProtocol,client] GitilesPoller: No new commits.",
			},
			{
				line:          "2015-09-27 23:41:00+1000 [HTTPChannel,44506,127.0.0.1] Loading builder Android's build 39149 from on-disk pickle",
				wantSuccess:   true,
				wantTimestamp: "2015-09-27T23:41:00.000000+10:00",
				wantSeverity:  Default,
				wantPayload:   "HTTPChannel,44506,127.0.0.1] Loading builder Android's build 39149 from on-disk pickle",
			},
		})
}

type callbackParser struct {
	cb      func(line string) *Entry
	mergeCb func(line string, e *Entry) bool
}

func (p *callbackParser) ParseLogLine(line string) *Entry { return p.cb(line) }

func (p *callbackParser) MergeLogLine(line string, e *Entry) bool { return p.mergeCb(line, e) }
