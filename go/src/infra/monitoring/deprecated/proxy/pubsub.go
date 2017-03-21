// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"net/http"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/distribution"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"

	"cloud.google.com/go/pubsub"
	"golang.org/x/net/context"
	"google.golang.org/api/option"
)

var (
	// OAuth2 scopes to generate.
	pubsubScopes = []string{
		pubsub.ScopePubSub,
		auth.OAuthScopeEmail,
	}

	// Error returned by pullAckMessages to indicate that no messages were available.
	errNoMessages = errors.New("pubsub: no messages")

	messageCount = metric.NewCounter("mon_proxy/pubsub/message",
		"Count of messages pulled from pub/sub, by worker",
		nil,
		field.Int("worker"))
	ackCount = metric.NewCounter("mon_proxy/pubsub/ack",
		"Count of messages Ack'd, by success/failure",
		nil,
		field.String("result"))
	pullDurationMetric = metric.NewCumulativeDistribution("mon_proxy/pubsub/pull_duration",
		"Time taken to Pull messages from pub/sub, in milliseconds",
		&types.MetricMetadata{Units: types.Milliseconds},
		distribution.DefaultBucketer)
	ackDurationMetric = metric.NewCumulativeDistribution("mon_proxy/pubsub/ack_duration",
		"Time taken to Ack messages to pub/sub, in milliseconds",
		&types.MetricMetadata{Units: types.Milliseconds},
		distribution.DefaultBucketer)
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
	fs.StringVar(&c.topic, "pubsub-topic", "", "The name of the Pub/Sub topic.")
	fs.IntVar(&c.batchSize, "pubsub-batch-size", 0, "The Pub/Sub batch size. If <=0, default will be used.")
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
	Receive(sub string, workers int, cb func(context.Context, *pubsub.Message)) error
}

// pubSubServiceImpl is an implementation of the pubSubService that uses the
// Pub/Sub API.
type pubSubServiceImpl struct {
	ctx    context.Context
	client *pubsub.Client
}

func newPubSubService(ctx context.Context, config pubsubConfig, client *http.Client) (pubSubService, error) {
	if config.project == "" {
		return nil, errors.New("pubsub: you must supply a project")
	}
	pc, err := pubsub.NewClient(ctx, config.project, option.WithHTTPClient(client))
	if err != nil {
		return nil, err
	}
	return &pubSubServiceImpl{
		ctx:    ctx,
		client: pc,
	}, nil
}

func (s *pubSubServiceImpl) SubExists(sub string) (bool, error) {
	return s.client.Subscription(sub).Exists(s.ctx)
}

func (s *pubSubServiceImpl) CreatePullSub(sub string, topic string) error {
	_, err := s.client.CreateSubscription(s.ctx, sub, s.client.Topic(topic), 0, &pubsub.PushConfig{Endpoint: ""})
	return err
}

func (s *pubSubServiceImpl) TopicExists(topic string) (bool, error) {
	return s.client.Topic(topic).Exists(s.ctx)
}

func (s *pubSubServiceImpl) CreateTopic(topic string) error {
	_, err := s.client.CreateTopic(s.ctx, topic)
	return err
}

func (s *pubSubServiceImpl) Receive(subName string, workers int, cb func(context.Context, *pubsub.Message)) error {
	sub := s.client.Subscription(subName)
	sub.ReceiveSettings.MaxOutstandingMessages = workers
	return sub.Receive(s.ctx, cb)
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
	if config.topic == "" {
		return nil, errors.New("pubsub: you must supply a topic")
	}
	if config.batchSize <= 0 {
		return nil, errors.New("pubsub: batch size must be at least 1")
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

func (p *pubsubClient) receive(workers int, cb func(context.Context, *pubsub.Message)) error {
	return p.service.Receive(p.subscription, workers, cb)
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
