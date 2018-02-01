// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"io"
	"strings"
	"sync"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

type blockingPushBuffer struct {
	start, finish chan struct{}

	lock     sync.Mutex
	blocking bool
	entries  []Entry
}

func (b *blockingPushBuffer) Start(ctx context.Context) {
}

func (b *blockingPushBuffer) Send(ctx context.Context, e Entry) {
	b.lock.Lock()
	b.entries = append(b.entries, e)
	blocking := b.blocking
	b.lock.Unlock()
	if blocking {
		b.start <- struct{}{}
		<-b.finish
	}
}

func (b *blockingPushBuffer) Stop(ctx context.Context) error {
	return nil
}

func (b *blockingPushBuffer) setBlocking(blocking bool) {
	b.lock.Lock()
	b.blocking = blocking
	b.lock.Unlock()
}

func (b *blockingPushBuffer) getEntries() (out []Entry) {
	b.lock.Lock()
	out = append(out, b.entries...)
	b.lock.Unlock()
	return
}

func TestPipeReader(t *testing.T) {
	Convey("PipeReader", t, func() {
		ctx := testContext()

		id := ClientID{"foo", "bar", "baz"}

		Convey("works", func() {
			client := &fakeClient{}
			buf := NewPushBuffer(PushBufferOptions{Client: client})
			body := `
				line
						another

				last one
				`

			buf.Start(ctx)
			pipeReader := PipeReader{
				ClientID:   id,
				Source:     strings.NewReader(body),
				PushBuffer: buf,
				Parser:     NullParser(),
			}
			So(pipeReader.Run(ctx), ShouldBeNil)
			So(buf.Stop(ctx), ShouldBeNil)

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

			dropped := make(chan struct{}, 10)

			reader, writer := io.Pipe()
			go func() {
				_, err := writer.Write([]byte("first line\n"))
				c.So(err, ShouldBeNil)

				// Wait for drainChannel to call Send for the first time and then block.
				<-buf.start

				// Send another two lines while drainChannel is blocked on Send.
				// PipeFromReader will send the first one but drop the second one.
				_, err = writer.Write([]byte("second line\nthird line\n"))
				c.So(err, ShouldBeNil)

				// Wait for the dropped line to be reported.
				<-dropped

				// Exit from Send and don't block the next time.
				buf.setBlocking(false)
				buf.finish <- struct{}{}

				c.So(writer.Close(), ShouldBeNil)
			}()

			pipeReader := PipeReader{
				ClientID:       id,
				Source:         reader,
				PushBuffer:     &buf,
				Parser:         NullParser(),
				LineBufferSize: 1,
				OnLineDropped:  func() { dropped <- struct{}{} },
			}
			err := pipeReader.Run(ctx)

			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldEqual,
				"1 lines in total were dropped due to insufficient line buffer size")

			entries := buf.getEntries()
			So(len(entries), ShouldEqual, 2)
			So(entries[0].TextPayload, ShouldEqual, "first line")
			So(entries[1].TextPayload, ShouldEqual, "second line")

			So(droppedCounter.Get(ctx, "baz", "foo", "bar"), ShouldEqual, 1)
		})
	})
}
