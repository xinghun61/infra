// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"fmt"
	"net/http"
	"os"

	"go.chromium.org/luci/common/errors"
	gcps "go.chromium.org/luci/common/gcloud/pubsub"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"google.golang.org/api/googleapi"
	"google.golang.org/api/pubsub/v1"
	"google.golang.org/appengine"
)

const (
	// Topic/subscription name.
	name = "worker-completion"
	// The dispatcher can't route _ah URLs. To work around this limitation,
	// we address the module directly in the pubsub push URL.
	pushURLFormat = "https://driver-dot-%s.appspot.com/_ah/push-handlers/notify"
)

// PubSubAPI defines the interface to the pubsub server.
//
// The interface is tuned to the needs of Tricium.
type PubSubAPI interface {
	// Setup sets up a Pub/Sub subscription.
	//
	// The subscription will be connected to a topic derived from the instance context.
	// The topics should have the form:
	//   '/projects/tricium-dev/topics/worker-completion[-HOSTNAME]'
	// The hostname suffix should only be added for local dev server instances.
	//
	// This topic should already have been added before workflow launch, and should
	// have chromium-swarming[-dev] as owner.
	Setup(c context.Context) error

	// Pull pulls one pubsub message.
	Pull(c context.Context) (*pubsub.PubsubMessage, error)
}

// PubsubServer implements the PubSub interface.
var PubsubServer pubsubServer

type pubsubServer struct {
}

// Setup implements the PubSub interface.
func (pubsubServer) Setup(c context.Context) error {
	topic := topic(c)
	sub := subscription(c)
	pushURL := pushURL(c)
	logging.Fields{
		"topic":        topic,
		"subscription": subscription,
		"pushURL":      pushURL,
	}.Infof(c, "PubSub set up.")
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(pubsub.PubsubScope))
	if err != nil {
		return errors.Annotate(err, "failed to create HTTP transport").Err()
	}
	service, err := pubsub.New(&http.Client{Transport: transport})
	if err != nil {
		return errors.Annotate(err, "failed to create HTTP client").Err()
	}
	// Create the subscription to this topic. Ignore HTTP 409 (means the subscription already exists).
	_, err = service.Projects.Subscriptions.Create(sub, &pubsub.Subscription{
		Topic:              topic,
		AckDeadlineSeconds: 70, // GAE request timeout plus some spare time
		PushConfig: &pubsub.PushConfig{
			PushEndpoint: pushURL, // if "", the subscription will be pull based
		},
	}).Context(c).Do()
	if err != nil && !isHTTP409(err) {
		return errors.Annotate(err, "failed to check subscription").Err()
	}
	return nil
}

// Pull implements the PubSub interface.
func (pubsubServer) Pull(c context.Context) (*pubsub.PubsubMessage, error) {
	sub := subscription(c)
	logging.Fields{
		"subscription": sub,
	}.Infof(c, "Pub/Sub pull")
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(pubsub.PubsubScope))
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP transport").Err()
	}
	service, err := pubsub.New(&http.Client{Transport: transport})
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	// Pull one message.
	resp, err := service.Projects.Subscriptions.Pull(sub, &pubsub.PullRequest{
		ReturnImmediately: true,
		MaxMessages:       1,
	}).Context(c).Do()
	if err != nil {
		return nil, errors.Annotate(err, "failed to pull pubsub message").Err()
	}
	var msg *pubsub.PubsubMessage
	var ack func()
	switch len(resp.ReceivedMessages) {
	case 0:
		// Found no pubsub message.
		return nil, nil
	case 1:
		ackID := resp.ReceivedMessages[0].AckId
		ack = func() {
			_, err := service.Projects.Subscriptions.Acknowledge(sub, &pubsub.AcknowledgeRequest{
				AckIds: []string{ackID},
			}).Context(c).Do()
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to acknowledge PubSub message")
				return
			}
		}
		// Pulled one pubsub message.
		msg = resp.ReceivedMessages[0].Message
	default:
		panic(errors.Reason("received more than one message from PubSub while asking for only one").Err())
	}
	ack()
	return msg, nil
}

func isHTTP409(err error) bool {
	apiErr, _ := err.(*googleapi.Error)
	return apiErr != nil && apiErr.Code == 409
}

// topic returns the pubsub topic to use for worker completion notification.
//
// On the dev server, the Tricium dev instance is used and the topic is amended
// with a hostname suffix. For app engine instances, the app ID is used when
// composing the topic.
func topic(c context.Context) string {
	t := gcps.NewTopic(AppID(c), name+nameSuffix())
	return t.String()
}

// subscription returns the pubsub subscription name to use.
//
// On the dev server, the subscription has a hostname suffix and the push URL
// is set to "" to indicate pull subscription.
func subscription(c context.Context) string {
	s := gcps.NewSubscription(AppID(c), name+nameSuffix())
	return s.String()
}

func pushURL(c context.Context) string {
	if appengine.IsDevAppServer() {
		return ""
	}
	return fmt.Sprintf(pushURLFormat, AppID(c))
}

// A suffix to add to the end of topic and subscription names.
//
// This is used so that different names can be used for
// different developers when running devservers.
func nameSuffix() string {
	if appengine.IsDevAppServer() {
		return "-" + hostname()
	}
	return ""
}

// Cache the hostname to prevent unnecessary os calls.
var hostnameCache = ""

func hostname() string {
	if hostnameCache != "" {
		return hostnameCache
	}
	h, err := os.Hostname()
	if err != nil {
		h = "localhost"
	}
	hostnameCache = h
	return hostnameCache
}

// MockPubSub mocks the PubSub interface for testing.
var MockPubSub mockPubSub

type mockPubSub struct {
}

// Setup is a mock function for the PubSub interface.
//
// For any testing actually using the return value, create a new mock.
func (mockPubSub) Setup(c context.Context) error {
	return nil
}

// Pull is a mock function for the PubSub interface.
//
// For any testing actually using the return value, create a new mock.
func (mockPubSub) Pull(c context.Context) (*pubsub.PubsubMessage, error) {
	return nil, nil
}
