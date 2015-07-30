// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"testing"

	"github.com/luci/luci-go/common/retry"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	"google.golang.org/cloud/pubsub"
	"infra/monitoring/proxy/mock"
)

type endpointServiceMock struct {
	mock.Mock

	msgC chan []byte
}

var _ endpointService = (*endpointServiceMock)(nil)

func (s *endpointServiceMock) send(ctx context.Context, data []byte) (err error) {
	s.Pop("send", ctx, data).BindResult(&err)
	if err == nil && s.msgC != nil {
		s.msgC <- data
	}
	return
}

var _ pubSubService = (*testPubSubService)(nil)

func TestMain(t *testing.T) {
	t.Parallel()

	// Do not retry.
	ctx := retry.Use(context.Background(), func(context.Context) retry.Iterator {
		return &retry.Limited{}
	})

	Convey(`An application using testing stubs`, t, func() {
		config := config{
			pubsub: pubsubConfig{
				project:      "test-project",
				topic:        "test-topic",
				subscription: "test-subscription",
				create:       false,
				batchSize:    64,
			},
			endpoint: endpointConfig{
				url: "fake-protocol://test.endpoint",
			},
			numWorkers: 10,
		}

		pubsubMock := &testPubSubService{
			infinitePull: true,
		}
		endpointMock := &endpointServiceMock{
			msgC: make(chan []byte),
		}

		pubsubMock.MockCall("SubExists", "test-subscription").WithResult(true, nil)
		pubsubClient, err := newPubSubClient(ctx, config.pubsub, pubsubMock)
		So(err, ShouldBeNil)

		app := newApplication(config)
		app.pubsub = pubsubClient
		app.endpoint = endpointMock

		// Run the application. Shut down after each test is complete.
		finishedC := make(chan struct{})
		go func() {
			app.run(ctx)
			close(finishedC)
		}()
		defer func() {
			app.shutdown()
			<-finishedC

			So(pubsubMock, mock.ShouldHaveNoErrors)
			So(endpointMock, mock.ShouldHaveNoErrors)
		}()

		Convey(`Will consume messages from Pub/Sub.`, func() {
			buf := make([]byte, binary.MaxVarintLen64)
			missing := make(map[int]bool)
			for i := 0; i < 1024; i++ {
				missing[i] = true
				count := binary.PutUvarint(buf, uint64(i))

				msg := &pubsub.Message{
					ID:    fmt.Sprintf("msg-%d", i),
					AckID: fmt.Sprintf("ack-%d", i),
					Data:  make([]byte, count),
				}
				copy(msg.Data, buf)
				pubsubMock.MockCall("Pull", "test-subscription", 64).WithResult([]*pubsub.Message{msg}, nil)
				pubsubMock.MockCall("Ack", "test-subscription", []string{msg.AckID}).WithResult(nil)
				endpointMock.MockCall("send", mock.Ignore, msg.Data).WithResult(nil)
			}

			missingCount := len(missing)
			for i := 0; i < 1024; i++ {
				msg := <-endpointMock.msgC
				index, _ := binary.Uvarint(msg)

				v := missing[int(index)]
				So(v, ShouldBeTrue)

				missing[int(index)] = false
				missingCount--
			}
			So(missingCount, ShouldEqual, 0)
		})

		Convey(`Will refuse to process a message that is too large, and will ACK it.`, func() {
			msgs := []*pubsub.Message{
				{
					ID:    "msg-big",
					AckID: "ack-big",
					Data:  bytes.Repeat([]byte{0xAA}, maxMessageSize+1),
				},
				{
					ID:    "msg-legit",
					AckID: "ack-legit",
					Data:  bytes.Repeat([]byte{0x55}, maxMessageSize),
				},
			}

			pubsubMock.MockCall("Pull", "test-subscription", 64).WithResult(msgs, nil)
			pubsubMock.MockCall("Ack", "test-subscription", []string{"ack-big", "ack-legit"}).WithResult(nil)
			endpointMock.MockCall("send", mock.Ignore, msgs[1].Data).WithResult(nil)

			So(<-endpointMock.msgC, ShouldResemble, msgs[1].Data)
		})
	})
}
