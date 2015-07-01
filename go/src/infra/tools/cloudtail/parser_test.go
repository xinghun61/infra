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

type callbackParser struct {
	cb func(line string) *Entry
}

func (p *callbackParser) ParseLogLine(line string) *Entry { return p.cb(line) }
