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
	"infra/monitoring/proxy/mock"
)

// testPubSubService implements pubSubService using testing stubs.
type testPubSubService struct {
	mock.Mock

	infinitePull bool
}

var _ pubSubService = (*testPubSubService)(nil)

func (s *testPubSubService) SubExists(sub string) (exists bool, err error) {
	s.Pop("SubExists", sub).BindResult(&exists, &err)
	return
}

func (s *testPubSubService) CreatePullSub(sub string, topic string) (err error) {
	s.Pop("CreatePullSub", sub, topic).BindResult(&err)
	return
}

func (s *testPubSubService) TopicExists(topic string) (exists bool, err error) {
	s.Pop("TopicExists", topic).BindResult(&exists, &err)
	return
}

func (s *testPubSubService) CreateTopic(topic string) (err error) {
	s.Pop("CreateTopic", topic).BindResult(&err)
	return
}

func (s *testPubSubService) Pull(sub string, count int) (msgs []*pubsub.Message, err error) {
	mock, e := s.PopErr("Pull", sub, count)
	if e != nil {
		if s.infinitePull {
			return nil, nil
		}
		s.AddError(errors.New("out of mock Pull entries"))
	}

	mock.BindResult(&msgs, &err)
	return
}

func (s *testPubSubService) Ack(sub string, ackIDs []string) (err error) {
	s.Pop("Ack", sub, ackIDs).BindResult(&err)
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
		defer So(svc, mock.ShouldHaveNoErrors)

		Convey(`When the subscription does not exist`, func() {
			svc.MockCall("SubExists", "test-subscription").WithResult(false, nil)

			Convey(`And the topic does not exist, will create a new topic and subscription.`, func() {
				svc.MockCall("TopicExists", "test-topic").WithResult(false, nil)
				svc.MockCall("CreateTopic", "test-topic").WithResult(nil)
				svc.MockCall("CreatePullSub", "test-subscription", "test-topic").WithResult(nil)

				_, err := newPubSubClient(ctx, config, svc)
				So(err, ShouldBeNil)
			})

			Convey(`And the topic exists, will create a new subscription.`, func() {
				svc.MockCall("TopicExists", "test-topic").WithResult(true, nil)
				svc.MockCall("CreatePullSub", "test-subscription", "test-topic").WithResult(nil)

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
			svc.MockCall("SubExists", "test-subscription").WithResult(true, nil)

			client, err := newPubSubClient(ctx, config, svc)
			So(err, ShouldBeNil)

			Convey(`When executing pull/ack with no messages`, func() {
				svc.MockCall("Pull", "test-subscription", 64).WithResult(nil, nil)

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
				svc.MockCall("Pull", "test-subscription", 64).WithResult(msgs, nil)

				Convey(`Returns and ACKs that message.`, func() {
					svc.MockCall("Ack", "test-subscription", []string{"ack0"}).WithResult(nil)

					var pullMsg []*pubsub.Message
					err := client.pullAckMessages(ctx, func(msg []*pubsub.Message) {
						pullMsg = msg
					})
					So(err, ShouldBeNil)

					So(pullMsg, ShouldResemble, msgs)
				})

				Convey(`ACKs the message even if the handler panics.`, func() {
					svc.MockCall("Ack", "test-subscription", []string{"ack0"}).WithResult(nil)

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
				svc.MockCall("Pull", "test-subscription", 64).WithResult(nil, e)

				Convey(`Returns the error as transient.`, func() {
					So(client.pullAckMessages(ctx, func([]*pubsub.Message) {}), ShouldResemble, luciErrors.Transient{Err: e})
				})
			})
		})
	})
}
