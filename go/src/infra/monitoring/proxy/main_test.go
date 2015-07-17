// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/binary"
	"fmt"
	"testing"

	"github.com/luci/luci-go/common/retry"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	"google.golang.org/cloud/pubsub"
)

type endpointServiceMock struct {
	mockStruct

	msgC chan []byte
}

var _ endpointService = (*endpointServiceMock)(nil)

func (s *endpointServiceMock) send(ctx context.Context, data []byte) (err error) {
	s.pop("send", ctx, data).bindResult(&err)
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
		defer So(pubsubMock.remaining(), ShouldBeNil)

		endpointMock := &endpointServiceMock{}
		defer So(endpointMock.remaining(), ShouldBeNil)

		pubsubMock.mock("SubExists", "test-subscription").withResult(true, nil)
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
		}()

		Convey(`Will consume messages from Pub/Sub.`, func() {
			endpointMock.msgC = make(chan []byte)

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
				pubsubMock.mock("Pull", "test-subscription", 64).withResult([]*pubsub.Message{msg}, nil)
				pubsubMock.mock("Ack", "test-subscription", []string{msg.AckID}).withResult(nil)
				endpointMock.mock("send", mockIgnore, msg.Data).withResult(nil)
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
	})
}
