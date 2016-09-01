// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"io"
	"strings"
	"testing"

	"github.com/luci/luci-go/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

type blockingPushBuffer struct {
	blocking      bool
	start, finish chan struct{}

	entries []Entry
}

func (b *blockingPushBuffer) Add(e []Entry) {
	b.entries = append(b.entries, e...)
	if b.blocking {
		b.start <- struct{}{}
		<-b.finish
	}
}

func (b *blockingPushBuffer) Stop(abort <-chan struct{}) error {
	return nil
}

func TestPipeFromReader(t *testing.T) {
	Convey("PipeFromReader", t, func() {
		ctx := context.Background()
		ctx, _ = tsmon.WithDummyInMemory(ctx)

		id := ClientID{"foo", "bar", "baz"}

		Convey("works", func() {
			client := &fakeClient{}
			buf := NewPushBuffer(PushBufferOptions{Client: client})
			body := `
        line
            another

        last one
        `

			PipeFromReader(id, strings.NewReader(body), NullParser(), buf, ctx, 0)
			So(buf.Stop(nil), ShouldBeNil)

			text := []string{}
			for _, e := range client.getEntries() {
				text = append(text, e.TextPayload)
			}
			So(text, ShouldResemble, []string{"line", "another", "last one"})
		})

		Convey("is buffered and non-blocking", func(c C) {
			buf := blockingPushBuffer{
				blocking: true,
				start:    make(chan struct{}),
				finish:   make(chan struct{}),
			}

			reader, writer := io.Pipe()
			go func() {
				_, err := writer.Write([]byte("first line\n"))
				c.So(err, ShouldBeNil)

				// Wait for drainChannel to call Add for the first time.
				<-buf.start

				// Send another two lines while drainChannel is blocked on Add.
				// PipeFromReader will send the first one but drop the second one.
				_, err = writer.Write([]byte("second line\nthird line\n"))
				c.So(err, ShouldBeNil)

				// Exit from Add and don't block the next time.
				buf.blocking = false
				buf.finish <- struct{}{}

				c.So(writer.Close(), ShouldBeNil)
			}()

			PipeFromReader(id, reader, NullParser(), &buf, ctx, 1)
			So(len(buf.entries), ShouldEqual, 2)
			So(buf.entries[0].TextPayload, ShouldEqual, "first line")
			So(buf.entries[1].TextPayload, ShouldEqual, "second line")

			droppedCount, err := droppedCounter.Get(ctx, "baz", "foo", "bar")
			So(err, ShouldBeNil)
			So(droppedCount, ShouldEqual, 1)
		})
	})
}
