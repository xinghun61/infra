// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"testing"
	"time"

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
			t.Errorf("%d: ParseLogLine('%s').Timestamp -> %v, want %v", i, test.line, got.Timestamp.Format(timeLayout), test.wantTimestamp)
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
			{
				line:          "[I2015-10-27T06:59:24.219355 29084 140208595912448 lib.botmap:403] Checking swarming botmap updates...",
				wantSuccess:   true,
				wantTimestamp: "2015-10-27T06:59:24.219355+00:00",
				wantSeverity:  Info,
				wantPayload:   "29084 lib.botmap:403] Checking swarming botmap updates...",
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

func TestPuppetLogsParser(t *testing.T) {
	testTextLogsParser(t, &puppetLogsParser{},
		[]textTestCase{
			{
				line:        "not a valid log line",
				wantSuccess: false,
			},
			{
				line:          "Thu Oct 22 22:42:42 -0700 2015 Puppet (notice): Compiled catalog for vm8-m4.golo.chromium.org in environment production in 0.30 seconds",
				wantSuccess:   true,
				wantTimestamp: "2015-10-22T22:42:42.000000-07:00",
				wantSeverity:  Notice,
				wantPayload:   "Puppet: Compiled catalog for vm8-m4.golo.chromium.org in environment production in 0.30 seconds",
			},
			{
				line:          "Thu Oct 22 22:44:00 +1000 2015 Puppet (warning): Ignoring invalid UTF-8 byte sequences in data to be sent to PuppetDB",
				wantSuccess:   true,
				wantTimestamp: "2015-10-22T22:44:00.000000+10:00",
				wantSeverity:  Warning,
				wantPayload:   "Puppet: Ignoring invalid UTF-8 byte sequences in data to be sent to PuppetDB",
			},
		})
}

func TestApacheErrorLogsParser(t *testing.T) {
	testTextLogsParser(t, &apacheErrorLogsParser{
		localTimeZone: time.FixedZone("", -7*60*60),
	}, []textTestCase{
		{
			line:        "not a valid log line",
			wantSuccess: false,
		},
		{
			line:          "[Thu Oct 22 23:27:26 2015] [error] [client 192.168.70.8] Certificate Verification: Error (23): certificate revoked",
			wantSuccess:   true,
			wantTimestamp: "2015-10-22T23:27:26.000000-07:00",
			wantSeverity:  Error,
			wantPayload:   "[192.168.70.8] Certificate Verification: Error (23): certificate revoked",
		},
	})
}

type callbackParser struct {
	cb      func(line string) *Entry
	mergeCb func(line string, e *Entry) bool
}

func (p *callbackParser) ParseLogLine(line string) *Entry { return p.cb(line) }

func (p *callbackParser) MergeLogLine(line string, e *Entry) bool { return p.mergeCb(line, e) }
