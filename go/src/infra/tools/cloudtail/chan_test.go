// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDrainChannel(t *testing.T) {
	Convey("Works", t, func() {
		ctx := testContext()
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

		buf.Start(ctx)
		drainChannel(ctx, ch, NullParser(), buf)
		So(buf.Stop(ctx), ShouldBeNil)

		text := []string{}
		for _, e := range client.getEntries() {
			text = append(text, e.TextPayload)
		}
		So(text, ShouldResemble, []string{"normal line", "to be trimmed"})
	})

	Convey("Rejects unparsed lines", t, func() {
		ctx := testContext()
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

		buf.Start(ctx)
		drainChannel(ctx, ch, parser, buf)
		So(buf.Stop(ctx), ShouldBeNil)
		So(len(client.getEntries()), ShouldEqual, 0)
	})
}

func TestComputeInsertID(t *testing.T) {
	Convey("Text with TS", t, func() {
		id, err := computeInsertID(&Entry{
			Timestamp:   time.Unix(1435788505, 12345),
			TextPayload: "Hi",
		})
		So(err, ShouldBeNil)
		So(id, ShouldEqual, "1435788505000012345:lN2eCMEpx4X38lbo")
	})

	Convey("Text without TS", t, func() {
		id, err := computeInsertID(&Entry{
			TextPayload: "Hi",
		})
		So(err, ShouldBeNil)
		So(id, ShouldEqual, ":lN2eCMEpx4X38lbo")
	})

	Convey("JSON", t, func() {
		id, err := computeInsertID(&Entry{
			JSONPayload: struct {
				A int
				B int
			}{10, 20},
		})
		So(err, ShouldBeNil)
		So(id, ShouldEqual, ":dJ9ZWHLGN9BWUyLG")
	})
}
