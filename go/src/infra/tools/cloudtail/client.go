// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"

	"golang.org/x/net/context"
	"google.golang.org/api/googleapi"
	cloudlog "google.golang.org/api/logging/v2"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

// DefaultResourceType is used by NewClient if ClientOptions doesn't specify
// ResourceType.
const DefaultResourceType = "machine"

// Entry is a single log entry. It can be a text message, or a JSONish struct.
type Entry struct {
	// InsertId can be used to deduplicate log entries.
	InsertID string

	// Timestamp is an optional timestamp.
	Timestamp time.Time

	// Severity is the severity of the log entry.
	Severity Severity

	// TextPayload is the log entry payload, represented as a text string.
	TextPayload string

	// JSONPayload is the log entry payload, represented as a JSONish structure.
	JSONPayload interface{}

	// ParsedBy is the parser that parsed this line, or nil if it fell through to
	// the default parser.
	ParsedBy LogParser

	// Labels is a set of user-defined (key, value) data for additional
	// information about the log entry.
	Labels map[string]string
}

// Client knows how to send entries to Cloud Logging log.
type Client interface {
	// PushEntries sends entries to Cloud Logging. No retries.
	//
	// May return fatal or transient errors. Check with errors.IsTransient.
	//
	// Respects context deadline.
	PushEntries(ctx context.Context, entries []*Entry) error
}

// ClientID uniquely identifies the log entries sent by this process.
//
// Its values are used to identify the log in Cloud Logging and also included in
// monitoring metrics.
type ClientID struct {
	// ResourceType identifies a kind of entity that produces this log (e.g.
	// 'machine', 'master'). Default is DefaultResourceType.
	ResourceType string

	// ResourceID identifies exact instance of provided resource type (e.g
	// 'vm12-m4', 'master.chromium.fyi'). Default is machine hostname.
	ResourceID string

	// LogID identifies what sort of log this is. Must be set.
	LogID string
}

// ClientOptions is passed to NewClient.
type ClientOptions struct {
	// ClientID uniquely identifies the log entries sent by this process.
	ClientID

	// Client is http.Client to use (that must implement proper authentication).
	Client *http.Client

	// UserAgent is an optional string appended to User-Agent HTTP header.
	UserAgent string

	// ProjectID is Cloud project to sends logs to. Must be set.
	ProjectID string

	// Debug is true to print log entries to stdout instead of sending them.
	Debug bool
}

var (
	entriesCounter = metric.NewCounter("cloudtail/log_entries",
		"Log entries processed",
		nil,
		field.String("log"),
		field.String("resource_type"),
		field.String("resource_id"),
		field.String("severity"))
	writesCounter = metric.NewCounter("cloudtail/api_writes",
		"Writes to Cloud Logging API",
		nil,
		field.String("log"),
		field.String("resource_type"),
		field.String("resource_id"),
		field.String("result"))
)

const (
	minBackoffSleep = 5 * time.Second
	maxBackoffSleep = 15 * time.Minute
)

// NewClient returns new object that knows how to push log entries to a single
// log in Cloud Logging.
func NewClient(opts ClientOptions) (Client, error) {
	if opts.ProjectID == "" {
		return nil, fmt.Errorf("no ProjectID is provided")
	}
	if opts.ResourceType == "" {
		opts.ResourceType = DefaultResourceType
	}
	if opts.ResourceID == "" {
		var err error
		hostname, err := os.Hostname()
		if err != nil {
			return nil, err
		}
		opts.ResourceID = hostname
	}
	if opts.LogID == "" {
		return nil, fmt.Errorf("no LogID is provided")
	}
	service, err := cloudlog.New(opts.Client)
	if err != nil {
		return nil, err
	}
	service.UserAgent = opts.UserAgent

	client := &loggingClient{
		opts:    opts,
		service: service,
		logName: fmt.Sprintf("projects/%s/logs/%s", opts.ProjectID, url.QueryEscape(opts.LogID)),
	}

	if opts.ResourceType == DefaultResourceType {
		// For "machine" resource types, abuse "gce_instance" resource to have at
		// least some level of integration with Log Viewer.
		client.resource = &cloudlog.MonitoredResource{
			Type: "gce_instance",
			Labels: map[string]string{
				"project_id":  opts.ProjectID,
				"instance_id": opts.ResourceID,
			},
		}
		client.labels = map[string]string{
			"compute.googleapis.com/resource_id":   opts.ResourceID,
			"compute.googleapis.com/resource_type": "instance",
		}
	} else {
		// For all other resource types just put stuff in "global" resource, but
		// annotate logs with labels.
		client.resource = &cloudlog.MonitoredResource{
			Type: "global",
			Labels: map[string]string{
				"project_id": opts.ProjectID,
			},
		}
		client.labels = map[string]string{
			"cloudtail/resource_id":   opts.ResourceID,
			"cloudtail/resource_type": opts.ResourceType,
		}
	}

	if opts.Debug {
		client.writeFunc = client.debugWriteFunc
	} else {
		client.writeFunc = client.cloudLoggingWriteFunc
	}
	return client, nil
}

////////////////////////////////////////////////////////////////////////////////

type writeFunc func(ctx context.Context, req *cloudlog.WriteLogEntriesRequest) error

type loggingClient struct {
	opts    ClientOptions
	service *cloudlog.Service

	// To sleep on HTTP 429.
	lock         sync.Mutex
	backoffSleep time.Duration

	// These are passed to Cloud Logging v2 API as is.
	logName  string
	labels   map[string]string
	resource *cloudlog.MonitoredResource

	// writeFunc is mocked in tests.
	writeFunc writeFunc
}

func (c *loggingClient) PushEntries(ctx context.Context, entries []*Entry) error {
	req := cloudlog.WriteLogEntriesRequest{
		Entries:  make([]*cloudlog.LogEntry, len(entries)),
		LogName:  c.logName,
		Labels:   c.labels,
		Resource: c.resource,
	}
	for i, e := range entries {
		entry := &cloudlog.LogEntry{
			InsertId:    e.InsertID,
			Severity:    "DEFAULT",
			TextPayload: e.TextPayload,
			Labels:      e.Labels,
		}
		if e.JSONPayload != nil {
			p, err := json.Marshal(e.JSONPayload)
			if err != nil {
				return err
			}
			entry.JsonPayload = googleapi.RawMessage(p)
		}
		if e.Severity != "" {
			if err := e.Severity.Validate(); err != nil {
				logging.Warningf(ctx, "invalid severity, ignoring: %s", e.Severity)
			} else {
				entry.Severity = string(e.Severity)
			}
		}
		if !e.Timestamp.IsZero() {
			entry.Timestamp = e.Timestamp.UTC().Format(time.RFC3339Nano)
		}
		req.Entries[i] = entry
		entriesCounter.Add(ctx, 1, c.opts.LogID, c.opts.ResourceType, c.opts.ResourceID, entry.Severity)
	}
	if err := c.writeFunc(ctx, &req); err != nil {
		writesCounter.Add(ctx, 1, c.opts.LogID, c.opts.ResourceType, c.opts.ResourceID, "failure")
		return err
	}

	writesCounter.Add(ctx, 1, c.opts.LogID, c.opts.ResourceType, c.opts.ResourceID, "success")
	return nil
}

func (c *loggingClient) debugWriteFunc(ctx context.Context, req *cloudlog.WriteLogEntriesRequest) error {
	buf, err := json.MarshalIndent(req, "", "  ")
	if err != nil {
		return err
	}
	fmt.Printf("----------\n%s\n", string(buf))
	clock.Sleep(ctx, 30*time.Millisecond)
	fmt.Println("----------")
	if os.Getenv("CLOUDTAIL_DEBUG_EMULATE_429") != "" {
		c.sleepOnRateLimiting(ctx)
		return errors.New("emulated HTTP 429", transient.Tag)
	}
	return nil
}

func (c *loggingClient) cloudLoggingWriteFunc(ctx context.Context, req *cloudlog.WriteLogEntriesRequest) error {
	_, err := c.service.Entries.Write(req).Context(ctx).Do()
	if err == nil {
		c.lock.Lock()
		c.backoffSleep = 0
		c.lock.Unlock()
		return nil
	}

	if apiErr, _ := err.(*googleapi.Error); apiErr != nil {
		if apiErr.Code >= 500 {
			return transient.Tag.Apply(err)
		}
		// HTTP 429 error happens when Cloud Logging is trying to throttle request
		// rate. This is global condition, so we keep the sleeping logic in the
		// loggingClient itself.
		if apiErr.Code == 429 {
			c.sleepOnRateLimiting(ctx)
			return transient.Tag.Apply(err)
		}
		return err
	}

	// The context is dead? Probably fatal error then.
	if ctx.Err() != nil {
		return err
	}

	// Non API errors are usually transient, like connection timeout or DNS
	// resolution problems.
	return transient.Tag.Apply(err)
}

func (c *loggingClient) sleepOnRateLimiting(ctx context.Context) {
	c.lock.Lock()
	if c.backoffSleep == 0 {
		c.backoffSleep = minBackoffSleep
	} else {
		c.backoffSleep *= 2
		if c.backoffSleep > maxBackoffSleep {
			c.backoffSleep = maxBackoffSleep
		}
	}
	toSleep := c.backoffSleep
	c.lock.Unlock()

	logging.Warningf(ctx, "Received HTTP 429, sleeping %s", toSleep)
	clock.Sleep(ctx, toSleep)
}
