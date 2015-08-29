// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"net/http"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"
	"google.golang.org/cloud"
	"google.golang.org/cloud/pubsub"
)

const (
	// The maximum number of items that can be pulled from a subscription at once.
	maxSubscriptionPullSize = 100
)

var (
	// OAuth2 scopes to generate.
	pubsubScopes = []string{
		pubsub.ScopePubSub,
		auth.OAuthScopeEmail,
	}

	// Error returned by pullAckMessages to indicate that no messages were available.
	errNoMessages = errors.New("pubsub: no messages")
)

// pubsubConfig is the set of configuration parameters for a pubsubClient.
type pubsubConfig struct {
	project      string // The project name.
	topic        string // The topic name.
	subscription string // The subscription name.
	create       bool
	batchSize    int // The number of elements to pull from a subscription per batch.
}

// addFlags adds this configuration's set of flags to a FlagSet.
func (c *pubsubConfig) addFlags(fs *flag.FlagSet) {
	fs.StringVar(&c.project, "pubsub-project", "", "The name of the Pub/Sub project.")
	fs.StringVar(&c.subscription, "pubsub-subscription", "", "The name of the Pub/Sub subscription.")
	fs.StringVar(&c.topic, "pubsub-topic", "",
		"The name of the Pub/Sub topic. Needed if subscription must be created.")
	fs.IntVar(&c.batchSize, "pubsub-batch-size", maxSubscriptionPullSize,
		"The Pub/Sub batch size.")
	fs.BoolVar(&c.create, "pubsub-create", false,
		"Create the subscription and/or topic if they don't exist.")
}

// pubSubService is an interface built around the actual Cloud PubSub API.
//
// TODO(dnj): Replace with github.com/luci/luci-go/common/gcloud/gcps#PubSub
// once it expresses create methods.
type pubSubService interface {
	SubExists(string) (bool, error)
	CreatePullSub(sub string, topic string) error
	TopicExists(string) (bool, error)
	CreateTopic(string) error
	Pull(sub string, count int) ([]*pubsub.Message, error)
	Ack(string, []string) error
}

// pubSubServiceImpl is an implementation of the pubSubService that uses the
// Pub/Sub API.
type pubSubServiceImpl struct {
	ctx context.Context
}

func newPubSubService(ctx context.Context, config pubsubConfig, client *http.Client) (pubSubService, error) {
	if config.project == "" {
		return nil, errors.New("pubsub: you must supply a project")
	}
	return &pubSubServiceImpl{
		ctx: cloud.WithContext(ctx, config.project, client),
	}, nil
}

func (s *pubSubServiceImpl) SubExists(sub string) (bool, error) {
	return pubsub.SubExists(s.ctx, sub)
}

func (s *pubSubServiceImpl) CreatePullSub(sub string, topic string) error {
	return pubsub.CreateSub(s.ctx, sub, topic, 0, "")
}

func (s *pubSubServiceImpl) TopicExists(topic string) (bool, error) {
	return pubsub.TopicExists(s.ctx, topic)
}

func (s *pubSubServiceImpl) CreateTopic(topic string) error {
	return pubsub.CreateTopic(s.ctx, topic)
}

func (s *pubSubServiceImpl) Pull(sub string, count int) ([]*pubsub.Message, error) {
	return pubsub.Pull(s.ctx, sub, count)
}

func (s *pubSubServiceImpl) Ack(sub string, ackIDs []string) error {
	return pubsub.Ack(s.ctx, sub, ackIDs...)
}

// A pubsubClient interfaces with a Cloud Pub/Sub subscription.
type pubsubClient struct {
	*pubsubConfig

	ctx     context.Context // A Context bound to PubSub authentication parameters.
	service pubSubService   // The backing Pub/Sub service.
}

// newPubSubClient instantiates a new Pub/Sub client.
//
// This method will also perform authentication and setup the topic/subscription
// if it isn't already set up.
func newPubSubClient(ctx context.Context, config pubsubConfig, svc pubSubService) (*pubsubClient, error) {
	if config.subscription == "" {
		return nil, errors.New("pubsub: you must supply a subscription")
	}
	if config.batchSize <= 0 {
		return nil, errors.New("pubsub: batch size must be at least 1")
	} else if config.batchSize > maxSubscriptionPullSize {
		return nil, fmt.Errorf("pubsub: batch size cannot exceed %d", maxSubscriptionPullSize)
	}

	p := pubsubClient{
		pubsubConfig: &config,
		service:      svc,
	}

	// Ensure that our Subscription (and topic) exist.
	if err := p.setupSubscription(ctx); err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to set up subscription.")
		return nil, err
	}

	return &p, nil
}

// setupSubscription asserts that the configured subscription exists. In doing
// so, it also asserts that the client credentials are valid with respect to the
// configured project/subscription.
//
// If the subscription doesn't exist, this method can create the subscription
// and (if missing) its topic, if the "create" flag is set.
func (p *pubsubClient) setupSubscription(ctx context.Context) error {
	exists := false
	log.Fields{
		"subscription": p.topic,
	}.Infof(ctx, "Checking for subscription existence.")
	err := retryCall(ctx, "SubExists()", func() error {
		var err error
		exists, err = p.service.SubExists(p.subscription)
		return p.wrapTransient(err)
	})
	if err != nil {
		log.Warningf(log.SetError(ctx, err),
			"Failed to test for subscription; assuming it doesn't exist.")
	}
	if exists {
		return nil
	}

	if !p.create {
		return errors.New("pubsub: subscription doesn't exist, not configured to create")
	}

	// Create the subscription if it doesn't exist.
	if p.topic == "" {
		log.Errorf(ctx, "Cannot create subscription; no topic was specified.")
		return errors.New("pubsub: cannot create subscription")
	}

	// Test if the topic exists...
	log.Fields{
		"topic": p.topic,
	}.Infof(ctx, "Checking for topic existence.")
	err = retryCall(ctx, "TopicExists()", func() error {
		var err error
		exists, err = p.service.TopicExists(p.topic)
		return p.wrapTransient(err)
	})
	if err != nil {
		log.Warningf(log.SetError(ctx, err),
			"Failed to test for topic; assuming it doesn't exist.")
	}

	if !exists {
		log.Fields{
			"topic": p.topic,
		}.Infof(ctx, "Creating topic.")
		err := retryCall(ctx, "CreateTopic()", func() error {
			return p.service.CreateTopic(p.topic)
		})
		if err != nil {
			log.Warningf(log.SetError(ctx, err),
				"Failed to create topic.")
			return errors.New("pubsub: cannot create topic")
		}
	}

	log.Fields{
		"topic":        p.topic,
		"subscription": p.subscription,
	}.Infof(ctx, "Creating pull subscription for topic.")
	if err := retryCall(ctx, "CreateSub()", func() error {
		return p.service.CreatePullSub(p.subscription, p.topic)
	}); err != nil {
		log.Warningf(log.SetError(ctx, err),
			"Failed to test for subscription; assuming it doesn't exist.")
		return errors.New("pubsub: failed to create subscription")
	}

	return nil
}

// pullAckMessages pulls a set of messages from the configured Subscription.
// If no messages are available, errNoMessages will be returned.
//
// handler is a method that returns true if there was a transient failure,
// indicating that the messages shouldn't be ACK'd.
func (p *pubsubClient) pullAckMessages(ctx context.Context, handler func([]*pubsub.Message)) error {
	var err error
	var msgs []*pubsub.Message
	ackCount := 0

	// Report the duration of a Pull/ACK cycle.
	startTime := clock.Now(ctx)
	defer func() {
		duration := clock.Now(ctx).Sub(startTime)
		log.Fields{
			"count":    len(msgs),
			"ackCount": ackCount,
			"duration": duration,
		}.Infof(ctx, "Pull/ACK cycle complete.")
	}()

	err = retryCall(ctx, "Pull()", func() error {
		var err error
		msgs, err = p.service.Pull(p.subscription, p.batchSize)
		return p.wrapTransient(err)
	})
	log.Fields{
		log.ErrorKey: err,
		"duration":   clock.Now(ctx).Sub(startTime),
		"count":      len(msgs),
	}.Debugf(ctx, "Pull() complete.")

	if err != nil {
		return err
	}

	if len(msgs) == 0 {
		return errNoMessages
	}

	defer func() {
		ackCount, err = p.ackMessages(ctx, msgs)
		if err != nil {
			log.Warningf(log.SetError(ctx, err), "Failed to ACK messages!")
		}
	}()
	handler(msgs)
	return nil
}

// ackMessages ACKs the supplied messages. If a message is nil, it will be
// ignored.
func (p *pubsubClient) ackMessages(ctx context.Context, messages []*pubsub.Message) (int, error) {
	messageIds := make([]string, 0, len(messages))
	skipped := 0
	for _, msg := range messages {
		if msg != nil {
			messageIds = append(messageIds, msg.AckID)
		} else {
			skipped++
		}
	}
	if len(messageIds) == 0 {
		return 0, nil
	}

	startTime := clock.Now(ctx)
	ctx = log.SetFields(ctx, log.Fields{
		"count":   len(messageIds),
		"skipped": skipped,
	})
	err := retryCall(ctx, "Ack()", func() error {
		return p.wrapTransient(p.service.Ack(p.subscription, messageIds))
	})
	duration := clock.Now(ctx).Sub(startTime)

	if err != nil {
		log.Fields{
			log.ErrorKey: err,
			"duration":   duration,
		}.Errorf(ctx, "Failed to ACK messages.")
		return 0, err
	}

	log.Fields{
		"duration": duration,
	}.Debugf(ctx, "Successfully ACK messages.")
	return len(messageIds), nil
}

// wrapTransient examines the supplied error. If it's not a recognized error
// value, it is treated as transient.
//
// This is because, at the moment, the transiant nature of the pubsub return
// codes is not discernable, so we will error on the side of caution (retry).
func (*pubsubClient) wrapTransient(err error) error {
	switch err {
	case nil:
		return nil

	case context.Canceled:
		return err

	default:
		return errors.WrapTransient(err)
	}
}
