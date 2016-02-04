// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"crypto/rand"
	"encoding/base64"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/luci/luci-go/common/clock"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"golang.org/x/net/context"
	cloudlog "google.golang.org/api/logging/v1beta3"
	"google.golang.org/cloud/compute/metadata"
)

const (
	cloudLoggingGCEService = "compute.googleapis.com"

	// cloudLoggingBatchSize is the number of log messages that will be sent in a
	// single cloud logging publish request.
	cloudLoggingBatchSize = 50

	// Number of bytes of random number to read for a unique session ID.
	loggingSessionIDSize = 36
)

var (
	cloudLoggingScopes = []string{
		cloudlog.CloudPlatformScope,
	}
)

// loggerConfig is the configuration for logging.
//
// The logging system chooses to log to either console output (go-logging) or
// Google Cloud Logging based on configuration parameters.
type loggerConfig struct {
	gceAccount string

	projectName string
	logsID      string

	serviceName  string
	zone         string
	resourceType string
	resourceID   string
	region       string
	userID       string

	sessionID string
	labels    map[string]string
}

func newLoggerConfig() *loggerConfig {
	c := &loggerConfig{
		gceAccount: "default",
		logsID:     "monitoring_proxy",
	}
	if metadata.OnGCE() {
		c.preloadFromGCEMetadata()
	}
	return c
}

// addFlags adds logging flags to the supplied FlagSet.
func (c *loggerConfig) addFlags(fs *flag.FlagSet) {
	fs.StringVar(&c.gceAccount, "logging-gce-account", c.gceAccount,
		"When using GCE logging, the name of the account to bind to.")
	fs.StringVar(&c.logsID, "logging-cloud-logs-id", c.logsID,
		"For cloud logging, the log stream ID.")
	fs.StringVar(&c.serviceName, "logging-cloud-service", c.serviceName,
		"For cloud logging, the service name.")
	fs.StringVar(&c.projectName, "logging-cloud-project-name", c.projectName,
		"For cloud logging, the project name.")
	fs.StringVar(&c.resourceType, "logging-cloud-resource-type", c.resourceType,
		"For cloud logging, the instance name.")
	fs.StringVar(&c.resourceID, "logging-cloud-resource-id", c.resourceID,
		"For cloud logging, the instance ID.")
	fs.StringVar(&c.region, "logging-cloud-region", c.region,
		"For cloud logging, the region.")
	fs.StringVar(&c.userID, "logging-cloud-user", c.userID,
		"For cloud logging, the user ID.")
	fs.StringVar(&c.zone, "logging-cloud-zone", c.zone,
		"For cloud logging, the zone.")
}

// getLogger chooses a base logger instance to use.
//
// If we're running on GCE, we will use a "cloud logging" logger; otherwise,
// we will use a console logger.
//
// The returned function should be called on application termination to flush
// the logger.
func (c *loggerConfig) use(ctx context.Context, client *http.Client) (context.Context, func(), error) {
	if c.projectName == "" {
		return ctx, nil, errors.New("logging: You must supply a project name")
	}
	if c.resourceType == "" {
		return ctx, nil, errors.New("logging: You must supply a resource type")
	}
	if c.logsID == "" {
		return ctx, nil, errors.New("logging: You must supply a logs ID")
	}

	configCopy := *c
	configCopy.labels = make(map[string]string)
	for k, v := range c.labels {
		configCopy.labels[k] = v
	}
	if c.resourceType != "" {
		configCopy.labels["compute.googleapis.com/resource_type"] = c.resourceType
	}
	if c.resourceID != "" {
		configCopy.labels["compute.googleapis.com/resource_id"] = c.resourceID
	}

	if configCopy.sessionID == "" {
		sessionID := make([]byte, loggingSessionIDSize)
		if _, err := rand.Read(sessionID); err != nil {
			return ctx, nil, err
		}

		configCopy.sessionID = base64.URLEncoding.EncodeToString(sessionID)
	}

	// Load GCE credentials for cloud logger.
	service, err := cloudlog.New(client)
	if err != nil {
		return ctx, nil, err
	}

	clog := newCloudLogging(ctx, &configCopy, service)

	ctx = log.SetFactory(ctx, func(c context.Context) log.Logger {
		return clog.bind(c)
	})
	return ctx, clog.finish, nil
}

// preloadFromGCEMetadata loads fills the configuration with default values
// derived from GCE metadata querying. If any GCE metadata is missing, the flag
// will not be populated.
func (c *loggerConfig) preloadFromGCEMetadata() {
	get := func(f func() (string, error), val *string) {
		v, err := f()
		if err == nil {
			*val = v
		}
	}

	c.serviceName = cloudLoggingGCEService
	get(metadata.ProjectID, &c.projectName)
	get(metadata.InstanceName, &c.resourceType)
	get(metadata.InstanceID, &c.resourceID)
	get(metadata.Zone, &c.zone)
}

// Snapshot of a log entry.
type logEntry struct {
	timestamp time.Time
	level     log.Level
	fmt       string
	args      []interface{}
	fields    log.Fields
}

func (e *logEntry) String() string {
	return fmt.Sprintf("Log[timestamp=%s, level=%s, message=%s, fields=%s]",
		e.timestamp, e.level, fmt.Sprintf(e.fmt, e.args...), e.fields)
}

// cloudLogging is a logger instance that logs to Google Cloud Logging.
//
// This is a singleton system that will forward logs to Google Cloud Logging. It
// does not implement log.Logger; instead, the logger is dynamically generated
// via a log.Factory, binding the log call's Context to this singleton.
//
// This is necessary, as we need to pull log Fields from the log call's Context.
type cloudLogging struct {
	*loggerConfig

	ctx     context.Context // The context that we were created with.
	service *cloudlog.Service

	logC      chan *logEntry
	finishedC chan struct{}

	testLogAckC chan []*logEntry // (Testing) Channel to synchronize log ingest.
}

func newCloudLogging(ctx context.Context, config *loggerConfig, service *cloudlog.Service) *cloudLogging {
	l := &cloudLogging{
		loggerConfig: config,
		ctx:          ctx,
		service:      service,

		logC:      make(chan *logEntry, cloudLoggingBatchSize*4),
		finishedC: make(chan struct{}),
	}
	go l.process()
	return l
}

func (l *cloudLogging) finish() {
	close(l.logC)
	<-l.finishedC
}

func (l *cloudLogging) bind(ctx context.Context) *boundCloudLogger {
	return &boundCloudLogger{
		ctx:    ctx,
		logger: l,
	}
}

// process is run in a separate goroutine to pull log entries and publish them
// to cloud logging.
func (l *cloudLogging) process() {
	defer close(l.finishedC)

	entries := make([]*logEntry, cloudLoggingBatchSize)
	index := int64(0)
	for e := range l.logC {
		// Pull up to our entry capacity.
		entries[0] = e
		count := 1
		for count < len(entries) {
			found := false
			select {
			case moreE, ok := <-l.logC:
				if ok {
					entries[count] = moreE
					count++
					found = true
				}
			default:
				break
			}

			if !found {
				break
			}
		}

		// (Testing) Acknowledge processing the logs.
		if l.testLogAckC != nil {
			l.testLogAckC <- entries[:count]
		}

		if err := l.sendLogEntries(entries[:count], index); err != nil {
			// Output our transmission errors to STDERR :(
			for idx, e := range entries[:count] {
				fmt.Fprintf(os.Stderr, "ERROR: Failed to publish log entry #%d. {error=%s, log=%s}\n",
					idx, err, e)
			}
		}
		index++
	}
}

// sendLogEntries sends a logEntry bundle to the Cloud Logging system.
func (l *cloudLogging) sendLogEntries(entries []*logEntry, index int64) error {
	if len(entries) == 0 {
		return nil
	}

	logEntries := make([]*cloudlog.LogEntry, len(entries))
	for idx, e := range entries {
		logEntries[idx] = l.buildLogEntry(e, index, int64(idx))
	}

	req := cloudlog.WriteLogEntriesRequest{
		CommonLabels: l.labels,
		Entries:      logEntries,
	}

	svc := cloudlog.NewProjectsLogsEntriesService(l.service)
	call := svc.Write(l.projectName, l.logsID, &req)
	return retry.Retry(l.ctx, backoffPolicy(l.ctx), func() error {
		_, err := call.Do()
		return err
	}, func(err error, delay time.Duration) {
		// Write error to STDERR.
		fmt.Fprintf(os.Stderr, "WARNING: Failed to send log entries {err=%s, delay=%s, entries=%s}\n",
			err, delay, entries)
	})
}

// buildLogEntry constructs a Cloud Logging LogEntry from the supplied logEntry.
// This couples the logging subsystem to the Cloud Logging log structure.
func (l *cloudLogging) buildLogEntry(e *logEntry, streamIndex, logIndex int64) *cloudlog.LogEntry {
	// Add logging fields to labels.
	labels := make(map[string]string, len(e.fields))
	for k, v := range e.fields {
		labels[k] = fmt.Sprintf("%v", v)
	}

	md := cloudlog.LogEntryMetadata{
		Labels:      labels,
		ProjectId:   l.projectName,
		Region:      l.region,
		ServiceName: l.serviceName,
		Severity:    l.getSeverity(e.level),
		Timestamp:   l.formatTimestamp(e.timestamp),
		UserId:      l.userID,
		Zone:        l.zone,
	}

	text := fmt.Sprintf(e.fmt, e.args...)
	if len(e.fields) > 0 {
		text = strings.Join([]string{text, e.fields.String()}, " ")
	}

	return &cloudlog.LogEntry{
		InsertId:    l.generateInsertID(streamIndex, logIndex),
		Metadata:    &md,
		TextPayload: text,
	}
}

// generateInsertID generates a unique insert ID for the log. The uniqueness
// is guaranteed by:
//   - The session ID, a randomly-generated number.
//   - The stream index, which is incremented for each unique invocation to
//     sendLogEntries.
//   - The log index, which is generated for each logEntry within the
//     sendLogEntries call.
func (l *cloudLogging) generateInsertID(streamIndex, logIndex int64) string {
	return fmt.Sprintf("%s-%d-%d", l.sessionID, streamIndex, logIndex)
}

func (*cloudLogging) getSeverity(l log.Level) string {
	switch l {
	case log.Debug:
		return "DEBUG"
	case log.Info:
		return "INFO"
	case log.Warning:
		return "WARNING"
	case log.Error:
		return "ERROR"

	default:
		return "DEFAULT"
	}
}

// formatTimestamp formats a time.Time such that it is compatible with Cloud
// Logging timestamp.
func (*cloudLogging) formatTimestamp(t time.Time) string {
	return t.UTC().Format(time.RFC3339Nano)
}

// boundCloudLogger is a log.Logger implementation binding the current Context
// to the Cloud Logging singleton.
type boundCloudLogger struct {
	ctx    context.Context
	logger *cloudLogging
}

var _ log.Logger = (*boundCloudLogger)(nil)

func (l *boundCloudLogger) Debugf(fmt string, args ...interface{}) {
	l.LogCall(log.Debug, 0, fmt, args)
}
func (l *boundCloudLogger) Infof(fmt string, args ...interface{}) {
	l.LogCall(log.Info, 0, fmt, args)
}
func (l *boundCloudLogger) Warningf(fmt string, args ...interface{}) {
	l.LogCall(log.Warning, 0, fmt, args)
}
func (l *boundCloudLogger) Errorf(fmt string, args ...interface{}) {
	l.LogCall(log.Error, 0, fmt, args)
}

func (l *boundCloudLogger) LogCall(level log.Level, calldepth int, f string, args []interface{}) {
	if len(f) == 0 || !log.IsLogging(l.ctx, level) {
		return
	}

	l.logger.logC <- &logEntry{
		timestamp: clock.Now(l.ctx),
		level:     level,
		fmt:       f,
		args:      args,
		fields:    log.GetFields(l.ctx),
	}
}
