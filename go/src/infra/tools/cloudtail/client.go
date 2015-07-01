// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/luci/luci-go/common/logging"
	cloudlog "google.golang.org/api/logging/v1beta3"
)

// DefaultResourceType is used by NewClient if ClientOptions doesn't specify
// ResourceType.
const DefaultResourceType = "machine"

// Entry is a single log entry. It can be a text message, or a JSONish struct.
type Entry struct {
	// Timestamp is an optional timestamp.
	Timestamp time.Time
	// Severity is the severity of the log entry.
	Severity Severity
	// TextPayload is the log entry payload, represented as a text string.
	TextPayload string
	// StructPayload is the log entry payload, represented as a JSONish structure.
	StructPayload interface{}
}

// Client knows how to send entries to Cloud Logging log.
type Client interface {
	PushEntries(entries []Entry) error
}

// ClientOptions is passed to NewClient.
type ClientOptions struct {
	// Client is used http.Client (that must implement proper authentication).
	Client *http.Client
	// Logger is used to emit local log messages related to the client itself.
	Logger logging.Logger
	// UserAgent is an optional string appended to User-Agent HTTP header.
	UserAgent string
	// ProjectID is Cloud project to sends logs to. Must be set.
	ProjectID string
	// ResourceType identifies a kind of entity that produces this log (e.g.
	// 'machine', 'master'). Default is DefaultResourceType.
	ResourceType string
	// ResourceID identifies exact instance of provided resource type (e.g
	// 'vm12-m4', 'master.chromium.fyi'). Default is machine hostname.
	ResourceID string
	// LogID identifies what sort of log this is. Must be set.
	LogID string
}

// NewClient returns new object that knows how to push log entries to a single
// log in Cloud Logging.
func NewClient(opts ClientOptions) (Client, error) {
	if opts.Logger == nil {
		opts.Logger = logging.Null()
	}
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
	return &loggingClient{
		opts: opts,
		commonLabels: map[string]string{
			"compute.googleapis.com/resource_id":   opts.ResourceID,
			"compute.googleapis.com/resource_type": opts.ResourceType,
		},
		serviceName: "compute.googleapis.com",
		writeFunc: func(projID, logID string, req *cloudlog.WriteLogEntriesRequest) error {
			_, err := service.Projects.Logs.Entries.Write(projID, logID, req).Do()
			return err
		},
	}, nil
}

////////////////////////////////////////////////////////////////////////////////

type writeFunc func(projID, logID string, req *cloudlog.WriteLogEntriesRequest) error

type loggingClient struct {
	opts ClientOptions

	// These are passed to Cloud Loggin API as is.
	commonLabels map[string]string
	serviceName  string

	// writeFunc is mocked in tests.
	writeFunc writeFunc
}

func (c *loggingClient) PushEntries(entries []Entry) error {
	req := cloudlog.WriteLogEntriesRequest{
		CommonLabels: c.commonLabels,
		Entries:      make([]*cloudlog.LogEntry, len(entries)),
	}
	for i, e := range entries {
		metadata := &cloudlog.LogEntryMetadata{ServiceName: c.serviceName}
		if e.Severity != "" {
			if err := e.Severity.Validate(); err != nil {
				return err
			}
			metadata.Severity = string(e.Severity)
		}
		if !e.Timestamp.IsZero() {
			metadata.Timestamp = e.Timestamp.UTC().Format(time.RFC3339Nano)
		}
		req.Entries[i] = &cloudlog.LogEntry{
			Metadata:      metadata,
			TextPayload:   e.TextPayload,
			StructPayload: e.StructPayload,
		}
	}
	// TODO(vadimsh): Implement retry on transient errors and use InsertId to
	// deduplicate messages. Drop all unsent message for now to avoid clogging
	// the buffers in case of persistent send error.
	err := c.writeFunc(c.opts.ProjectID, c.opts.LogID, &req)
	if err != nil {
		c.opts.Logger.Errorf("dropping %d entries, error while sending: %s", len(entries), err)
	}
	return nil
}
