// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"testing"

	"github.com/luci/luci-go/common/logging"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDrainChannel(t *testing.T) {
	Convey("Works", t, func() {
		client := &fakeClient{}
		buf := NewPushBuffer(PushBufferOptions{Client: client})

		ch := make(chan string)
		go func() {
			ch <- "normal line"
			ch <- "  to be trimmed  "
			// Empty lines are skipped.
			ch <- ""
			ch <- "   "
			close(ch)
		}()

		drainChannel(ch, NullParser(), buf, nil)
		So(buf.Stop(), ShouldBeNil)

		text := []string{}
		for _, e := range client.getEntries() {
			text = append(text, e.TextPayload)
		}
		So(text, ShouldResemble, []string{"normal line", "to be trimmed"})
	})

	Convey("Rejects unparsed lines", t, func() {
		client := &fakeClient{}
		buf := NewPushBuffer(PushBufferOptions{Client: client})
		parser := &callbackParser{
			cb: func(string) *Entry { return nil },
		}

		ch := make(chan string)
		go func() {
			ch <- "normal line"
			close(ch)
		}()

		drainChannel(ch, parser, buf, logging.Null())
		So(buf.Stop(), ShouldBeNil)
		So(len(client.getEntries()), ShouldEqual, 0)
	})
}
