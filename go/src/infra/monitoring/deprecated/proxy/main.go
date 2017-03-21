// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"infra/libs/infraenv"
	"net/http"
	"os"
	"os/signal"
	"time"

	"cloud.google.com/go/pubsub"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/cloudlogging"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/cloudlog"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/distribution"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/common/tsmon/types"
	"golang.org/x/net/context"
)

const (
	// noMessageDelay is the amount of time to sleep after receiving no messages.
	noMessageDelay = 1 * time.Second

	// maxMessageSize is the maximum size of a message that the proxy will
	// forward. Messages larger than this will be discarded by policy.
	maxMessageSize = 1024 * 512
)

var (
	sentCount = metric.NewCounter("mon_proxy/endpoint/sent",
		"Count of messages proxied to the endpoint",
		nil,
		field.String("result"))
	sentDuration = metric.NewCumulativeDistribution("mon_proxy/endpoint/duration",
		"Time taken to send messages to the endpoint, in milliseconds",
		&types.MetricMetadata{Units: types.Milliseconds},
		distribution.DefaultBucketer)
)

func init() {
	// Increase idle connections per host, since we connect to basically two
	// hosts.
	if t, ok := http.DefaultTransport.(*http.Transport); ok {
		t.MaxIdleConnsPerHost = 10000
	}
}

type config struct {
	pubsub   pubsubConfig
	endpoint endpointConfig

	serviceAccountJSONPath string
	authInteractive        bool
	numWorkers             int // Number of subscription worker goroutines.
}

// addFlags adds configuration flags to the supplied FlagSet.
func (c *config) addFlags(fs *flag.FlagSet) {
	c.pubsub.addFlags(fs)
	c.endpoint.addFlags(fs)

	fs.StringVar(&c.serviceAccountJSONPath, "proxy-service-account-json", "",
		"The path to the service account JSON credentials to use for Pub/Sub and cloud logging.")
	fs.BoolVar(&c.authInteractive, "auth-interactive", false,
		"If true, purge credential cache and perform interactive authentication workflow.")
	fs.IntVar(&c.numWorkers, "workers", 1, "The number of subscription worker goroutines.")
}

func (c *config) createAuthenticatedClient(ctx context.Context) (*http.Client, error) {
	scopes := []string{}
	scopes = append(scopes, cloudlogging.CloudLoggingScopes...)
	scopes = append(scopes, pubsubScopes...)

	mode := auth.SilentLogin
	if c.authInteractive {
		mode = auth.InteractiveLogin
	}

	// Get our authenticated client.
	options := infraenv.DefaultAuthOptions()
	options.Scopes = scopes
	options.ServiceAccountJSONPath = c.serviceAccountJSONPath
	return auth.NewAuthenticator(ctx, mode, options).Client()
}

// application represents the main application state.
type application struct {
	*config

	pubsub   *pubsubClient
	endpoint endpointService
}

// newApplication instantiates a new application instance and its associated
// client instances.
func newApplication(c config) *application {
	// Create Endpoint client.
	app := application{
		config: &c,
	}
	return &app
}

func (a *application) loadServices(ctx context.Context, client *http.Client) error {
	var err error

	svc, err := newPubSubService(ctx, a.config.pubsub, client)
	if err != nil {
		return err
	}
	a.pubsub, err = newPubSubClient(ctx, a.config.pubsub, svc)
	if err != nil {
		return err
	}

	a.endpoint, err = a.config.endpoint.createService(ctx)
	if err != nil {
		return err
	}

	return nil
}

// run executes the application.
func (a *application) run() error {
	// Although we call pullAckMessages without backoff or a throttle, the calls
	// to the Pub/Sub service use retry library's exponential backoff, so we
	// don't need to implement DoS protection at this level.
	return a.pubsub.receive(a.numWorkers, func(ctx context.Context, msg *pubsub.Message) {
		if err := a.proxySingleMessage(ctx, msg); err != nil {
			log.Errorf(log.SetError(ctx, err), "Error sending messages to proxy.")
			sentCount.Add(ctx, 1, "failure")

			if errors.IsTransient(err) {
				// Transient error: retry.
				msg.Nack()
			} else {
				// Non-transient error: consume the message.
				msg.Ack()
			}
		} else {
			// Success: consume the message.
			sentCount.Add(ctx, 1, "success")
			msg.Ack()
		}
	})
}

func (a *application) proxySingleMessage(ctx context.Context, msg *pubsub.Message) error {
	startTime := clock.Now(ctx)
	defer func() {
		duration := clock.Now(ctx).Sub(startTime)
		sentDuration.Add(ctx, float64(duration/time.Millisecond))
	}()

	// TODO: Validate messages.
	ctx = log.SetFields(ctx, log.Fields{
		"size":      len(msg.Data),
		"messageID": msg.ID,
	})

	log.Debugf(ctx, "Sending data to monitoring endpoint.")

	// Refuse to transmit message if it's too large.
	if len(msg.Data) > maxMessageSize {
		log.Fields{
			"size":    len(msg.Data),
			"maxSize": maxMessageSize,
		}.Errorf(ctx, "Message exceeds maximum size threshold; discarding.")
		return errors.New("main: message is too large")
	}

	// Execute the request.
	return a.endpoint.send(ctx, msg.Data)
}

// mainImpl is the main execution function.
func mainImpl(args []string) int {
	// Install a console logger by default.
	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)

	clConfig := cloudlogging.ClientOptions{
		LogID: "monitoring_proxy",
	}
	logConfig := log.Config{Level: log.Debug}
	config := config{}

	tsmonConfig := tsmon.NewFlags()
	tsmonConfig.Flush = "auto"
	tsmonConfig.Target.TargetType = "task"
	tsmonConfig.Target.TaskServiceName = "monitoring_proxy"
	clConfig.Populate()

	fs := flag.CommandLine
	config.addFlags(fs)
	clConfig.AddFlags(fs)
	logConfig.AddFlags(fs)
	tsmonConfig.Register(fs)
	fs.Parse(args)

	if tsmonConfig.Endpoint == "" {
		tsmonConfig.Endpoint = fmt.Sprintf("pubsub://%s/%s", config.pubsub.project, config.pubsub.topic)
	}
	if tsmonConfig.Credentials == "" {
		tsmonConfig.Credentials = auth.GCEServiceAccount
	}
	if tsmonConfig.Target.TaskJobName == "" {
		tsmonConfig.Target.TaskJobName = config.pubsub.subscription
	}

	ctx = logConfig.Set(ctx)

	// Load authenticated client.
	client, err := config.createAuthenticatedClient(ctx)
	if err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to create authenticated service client.")
		return 1
	}

	// Setup cloud logging.
	clClient, err := cloudlogging.NewClient(clConfig, client)
	if err != nil {
		log.WithError(err).Warningf(ctx, "Failed to setup cloud logging")
	} else {
		// Buffer log entries, flush before exiting.
		buf := cloudlogging.NewBuffer(ctx, cloudlogging.BufferOptions{}, clClient)
		defer buf.StopAndFlush()

		// Replace the console logger.
		ctx = cloudlog.Use(ctx, cloudlog.Config{}, buf)
	}

	ctx, cancelFunc := context.WithCancel(ctx)
	defer cancelFunc()

	app := newApplication(config)
	if err := app.loadServices(ctx, client); err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to initialize services.")
		return 1
	}

	// Configure tsmon.
	if err := tsmon.InitializeFromFlags(ctx, &tsmonConfig); err != nil {
		log.Errorf(log.SetError(ctx, err), "Failed to initialize tsmon.")
		return 1
	}

	// Set up interrupt handler.
	signalC := make(chan os.Signal, 1)
	go func() {
		triggered := false
		for sig := range signalC {
			if !triggered {
				triggered = true

				log.Infof(log.SetField(ctx, "signal", sig),
					"Received signal; starting shutdown.")
				cancelFunc()
			} else {
				// Triggered multiple times; immediately shut down.
				os.Exit(1)
			}
		}
	}()
	signal.Notify(signalC, os.Interrupt, os.Kill)
	defer func() {
		signal.Stop(signalC)
		close(signalC)
	}()

	log.Infof(ctx, "Starting application execution...")
	if err := app.run(); err != nil {
		log.Errorf(log.SetError(ctx, err), "Error during application execution.")
		return 1
	}

	return 0
}

func main() {
	os.Exit(mainImpl(os.Args[1:]))
}
