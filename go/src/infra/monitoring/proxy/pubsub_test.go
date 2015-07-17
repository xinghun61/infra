// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"errors"
	"testing"

	luciErrors "github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/retry"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	"google.golang.org/cloud/pubsub"
)

// testPubSubService implements pubSubService using testing stubs.
type testPubSubService struct {
	mockStruct

	infinitePull bool
}

var _ pubSubService = (*testPubSubService)(nil)

func (s *testPubSubService) SubExists(sub string) (exists bool, err error) {
	s.pop("SubExists", sub).bindResult(&exists, &err)
	return
}

func (s *testPubSubService) CreatePullSub(sub string, topic string) (err error) {
	s.pop("CreatePullSub", sub, topic).bindResult(&err)
	return
}

func (s *testPubSubService) TopicExists(topic string) (exists bool, err error) {
	s.pop("TopicExists", topic).bindResult(&exists, &err)
	return
}

func (s *testPubSubService) CreateTopic(topic string) (err error) {
	s.pop("CreateTopic", topic).bindResult(&err)
	return
}

func (s *testPubSubService) Pull(sub string, count int) (msgs []*pubsub.Message, err error) {
	mock, e := s.popErr("Pull", sub, count)
	if e != nil {
		if s.infinitePull {
			return nil, nil
		}
		panic("Out of mock Pull entries.")
	}

	mock.bindResult(&msgs, &err)
	return
}

func (s *testPubSubService) Ack(sub string, ackIDs []string) (err error) {
	s.pop("Ack", sub, ackIDs).bindResult(&err)
	return
}

func TestPubSub(t *testing.T) {
	t.Parallel()

	Convey(`Using a testing Pub/Sub config`, t, func() {
		// Do not retry.
		ctx := retry.Use(context.Background(), func(context.Context) retry.Iterator {
			return &retry.Limited{}
		})

		config := pubsubConfig{
			project:      "test-project",
			topic:        "test-topic",
			subscription: "test-subscription",
			create:       true,
			batchSize:    64,
		}

		svc := &testPubSubService{}
		defer So(svc.remaining(), ShouldBeNil)

		Convey(`When the subscription does not exist`, func() {
			svc.mock("SubExists", "test-subscription").withResult(false, nil)

			Convey(`And the topic does not exist, will create a new topic and subscription.`, func() {
				svc.mock("TopicExists", "test-topic").withResult(false, nil)
				svc.mock("CreateTopic", "test-topic").withResult(nil)
				svc.mock("CreatePullSub", "test-subscription", "test-topic").withResult(nil)

				_, err := newPubSubClient(ctx, config, svc)
				So(err, ShouldBeNil)
			})

			Convey(`And the topic exists, will create a new subscription.`, func() {
				svc.mock("TopicExists", "test-topic").withResult(true, nil)
				svc.mock("CreatePullSub", "test-subscription", "test-topic").withResult(nil)

				_, err := newPubSubClient(ctx, config, svc)
				So(err, ShouldBeNil)
			})

			Convey(`Will fail to create a new client when "create" is false.`, func() {
				config.create = false

				_, err := newPubSubClient(ctx, config, svc)
				So(err, ShouldNotBeNil)
			})
		})

		Convey(`Will create a new client.`, func() {
			svc.mock("SubExists", "test-subscription").withResult(true, nil)

			client, err := newPubSubClient(ctx, config, svc)
			So(err, ShouldBeNil)

			Convey(`When executing pull/ack with no messages`, func() {
				svc.mock("Pull", "test-subscription", 64).withResult(nil, nil)

				Convey(`Returns errNoMessages.`, func() {
					err := client.pullAckMessages(ctx, func([]*pubsub.Message) {})
					So(err, ShouldEqual, errNoMessages)
				})
			})

			Convey(`When executing pull/ack with one message`, func() {
				msgs := []*pubsub.Message{
					&pubsub.Message{
						ID:    "id0",
						AckID: "ack0",
						Data:  []byte{0xd0, 0x65},
					},
				}
				svc.mock("Pull", "test-subscription", 64).withResult(msgs, nil)

				Convey(`Returns and ACKs that message.`, func() {
					svc.mock("Ack", "test-subscription", []string{"ack0"}).withResult(nil)

					var pullMsg []*pubsub.Message
					err := client.pullAckMessages(ctx, func(msg []*pubsub.Message) {
						pullMsg = msg
					})
					So(err, ShouldBeNil)

					So(pullMsg, ShouldResemble, msgs)
				})

				Convey(`ACKs the message even if the handler panics.`, func() {
					svc.mock("Ack", "test-subscription", []string{"ack0"}).withResult(nil)

					So(func() {
						client.pullAckMessages(ctx, func(msg []*pubsub.Message) {
							panic("Handler failure!")
						})
					}, ShouldPanic)
				})

				Convey(`Does not ACK the message if the handler clears it.`, func() {
					err := client.pullAckMessages(ctx, func(msg []*pubsub.Message) {
						for i := range msg {
							msg[i] = nil
						}
					})
					So(err, ShouldBeNil)
				})
			})

			Convey(`When executing pull/ack with an error`, func() {
				e := errors.New("TEST ERROR")
				svc.mock("Pull", "test-subscription", 64).withResult(nil, e)

				Convey(`Returns the error as transient.`, func() {
					So(client.pullAckMessages(ctx, func([]*pubsub.Message) {}), ShouldResemble, luciErrors.Transient{Err: e})
				})
			})
		})
	})
}
