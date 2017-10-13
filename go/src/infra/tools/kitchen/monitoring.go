// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
	"sync/atomic"
	"time"

	"infra/libs/bqschema/buildevent"
	"infra/libs/bqschema/tabledef"
	"infra/libs/eventupload"
	"infra/libs/infraenv"
	"infra/tools/kitchen/build"

	cipdVersion "go.chromium.org/luci/cipd/version"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/common/sync/parallel"

	"cloud.google.com/go/bigquery"
	"google.golang.org/api/option"

	"golang.org/x/net/context"
)

// monitoringEventSender is an interface for a concurrency-safe object that can
// accept event structs.
//
// It is designed to match an eventupload.Uploader. However, we use an interface
// here so we can capture output events for testing.
type monitoringEventSender interface {
	Put(context.Context, *tabledef.TableDef, interface{}) error
}

type bigQueryMonitoringEventSender struct {
	client *bigquery.Client
	count  int32
}

func (es *bigQueryMonitoringEventSender) Put(ctx context.Context, td *tabledef.TableDef, event interface{}) error {
	up := eventupload.NewUploader(ctx, es.client, td)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true
	if err := up.Put(ctx, event); err != nil {
		if pme, ok := err.(bigquery.PutMultiError); ok {
			for _, e := range pme {
				// We want to log this as a single line, since we're running this Put
				// in parallel.
				lines := make([]string, len(e.Errors))
				for i, subErr := range e.Errors {
					lines[i] = fmt.Sprintf("  Error #%d: %s", i, subErr)
				}
				logging.Errorf(ctx, "Failed to put row #%d (%q):\n%s", e.RowIndex, e.InsertID, strings.Join(lines, "\n"))
			}
		}
		return err
	}

	atomic.AddInt32(&es.count, 1)
	return nil
}

// Monitoring provides facilities to measure and report on the monitored aspects
// of a Kitchen run.
type Monitoring struct {
	executionStart time.Time
	executionEnd   time.Time
	result         *build.BuildRunResult
}

func (m *Monitoring) beginExecution(ctx context.Context) { m.executionStart = clock.Now(ctx).UTC() }
func (m *Monitoring) endExecution(ctx context.Context, result *build.BuildRunResult) {
	m.executionEnd = clock.Now(ctx).UTC()
	m.result = result
}

// SendBuildCompletedReport sends a build completed report to BigQuery event
// monitoring.
func (m *Monitoring) SendBuildCompletedReport(ctx context.Context, auth *AuthContext) error {
	// Set up BigQuery client authentication.
	ts, err := auth.Authenticator([]string{bigquery.Scope}).TokenSource()
	if err != nil {
		return errors.Annotate(err, "could not get token source").Err()
	}

	// Get a BigQuery client instance.
	client, err := bigquery.NewClient(ctx, infraenv.ChromeInfraEventsProject, option.WithTokenSource(ts))
	if err != nil {
		return errors.Annotate(err, "could not get BigQuery client instance").Err()
	}

	es := &bigQueryMonitoringEventSender{client, 0}
	err = m.sendReport(ctx, es)
	logging.Infof(ctx, "Uploaded %d monitoring event(s).", es.count)
	return err
}

func (m *Monitoring) sendReport(ctx context.Context, es monitoringEventSender) error {
	if m.result == nil {
		return errors.New("no execution result is installed")
	}

	// Generate our events.
	params := m.makeCommonEventParams(ctx)

	// Send events to BigQuery (in parallel).
	_ = parallel.FanOutIn(func(workC chan<- func() error) {
		// Send completed build event.
		workC <- func() error {
			if err := m.sendLegacyBuildCompletedEvent(ctx, es, params); err != nil {
				logging.WithError(err).Errorf(ctx, "Could not send legacy build completed event.")
			}
			return nil
		}

		// Send completed step events.
		workC <- func() error {
			if err := m.sendLegacyStepCompletedEvents(ctx, es, params); err != nil {
				logging.WithError(err).Errorf(ctx, "Could not send legacy step completed events.")
			}
			return nil
		}
	})
	return nil
}

func (m *Monitoring) makeCommonEventParams(ctx context.Context) *commonMonitoringParams {
	var p commonMonitoringParams
	if m.result.Annotations != nil {
		p.environ = m.result.Annotations.GetCommand().GetEnviron()
		p.propertiesJSON = make(map[string]string)

		m.forEachStep(func(st *milo.Step) {
			for _, prop := range st.Property {
				p.propertiesJSON[prop.Name] = prop.Value
			}
		})
	}

	// Load BuildBucket parameters.
	if v := p.propertiesJSON["buildbucket"]; v != "" {
		p.bbInfo.Decode(v)
	}

	return &p
}

func (m *Monitoring) sendLegacyBuildCompletedEvent(ctx context.Context, es monitoringEventSender, p *commonMonitoringParams) error {
	// Derive some completion values.
	//
	// We determine build scheduling time as the time when the build was created
	// in BuildBucket.
	executionDuration := m.executionEnd.Sub(m.executionStart)
	queueDuration := time.Duration(0)
	if bs := p.buildScheduledTime(); !bs.IsZero() {
		queueDuration = m.executionStart.Sub(bs)
	}

	// Transform our build result into a legacy build completed event.
	event := buildevent.CompletedBuildsLegacy{
		Master:              p.master(),
		Builder:             p.builder(),
		BuildNumber:         p.buildNumber(),
		BuildSchedMsec:      timeToMsec(p.buildScheduledTime()),
		BuildStartedMsec:    timeToMsec(m.executionStart),
		BuildFinishedMsec:   timeToMsec(m.executionEnd),
		HostName:            p.hostname(),
		Result:              getStepLegacyResultEnum(m.result.Annotations),
		QueueDurationS:      queueDuration.Seconds(),
		ExecutionDurationS:  executionDuration.Seconds(),
		TotalDurationS:      (executionDuration + queueDuration).Seconds(),
		PatchUrl:            p.patchURL(),
		BbucketId:           p.bbInfo.Build.ID,
		BbucketUserAgent:    p.bbInfo.Tag("user_agent"),
		HeadRevisionGitHash: p.stringProperty("got_revision"),

		BuildId:        p.buildID(),
		BbucketBucket:  p.bbInfo.Build.Bucket,
		BuildScheduled: p.buildScheduledTime(),
		BuildStarted:   m.executionStart,
		BuildFinished:  m.executionEnd,
	}

	// event.Result
	//
	// TODO: Use m.result.RecipeResult for this, once it's been improved.
	// (crbug.com/721576).
	if m.result.InfraFailure != nil {
		// Outside of the annotation protobuf, Kitchen may determine that there is
		// an infra failure. That should override our event report.
		event.Result = buildevent.ResultInfraFailure
	}

	// event.Recipes
	if r := m.result.Recipe; r != nil {
		event.Recipes = &buildevent.CompletedBuildsLegacy_Recipes{
			Name:       r.Name,
			Repository: r.Repository,
			Revision:   r.Revision,
		}
	}

	// event.Category
	switch p.stringProperty("category") {
	case "cq":
		event.Category = buildevent.CategoryCQ
	case "cq_experimental":
		event.Category = buildevent.CategoryCQExperimental
	case "git_cl_try":
		event.Category = buildevent.CategoryGitCLTry
	}

	// event.Swarming
	if v := p.swarmingHost(); v != "" {
		event.Swarming = &buildevent.CompletedBuildsLegacy_Swarming{
			Host:  v,
			RunId: p.swarmingRunID(),
		}
	}

	// event.Kitchen
	if v, err := cipdVersion.GetCurrentVersion(); err == nil {
		event.Kitchen = &buildevent.CompletedBuildsLegacy_Kitchen{
			Version: v.InstanceID,
		}
	}

	return es.Put(ctx, buildevent.CompletedBuildsLegacyTable, &event)
}

func (m *Monitoring) sendLegacyStepCompletedEvents(ctx context.Context, es monitoringEventSender, p *commonMonitoringParams) error {
	var events []*buildevent.CompletedStepLegacy
	stepNumber := int64(0)
	m.forEachStep(func(st *milo.Step) {
		if st.Name == "" {
			// Skip root step.
			return
		}

		event, err := m.makeLegacyStepCompletedEvent(ctx, p, st)
		if err != nil {
			logging.WithError(err).Errorf(ctx, "Failed to create completed step event for %q.", st.Name)
		}

		// Assign a step number.
		event.StepNumber = stepNumber
		stepNumber++

		events = append(events, event)
	})

	return es.Put(ctx, buildevent.CompletedStepLegacyTable, events)
}

func (m *Monitoring) makeLegacyStepCompletedEvent(ctx context.Context, p *commonMonitoringParams, st *milo.Step) (
	*buildevent.CompletedStepLegacy, error) {

	stepStarted := google.TimeFromProto(st.Started)
	stepFinished := google.TimeFromProto(st.Ended)

	stepDuration := time.Duration(0)
	if !(stepStarted.IsZero() || stepFinished.IsZero()) {
		stepDuration = stepFinished.Sub(stepStarted)
	}

	event := buildevent.CompletedStepLegacy{
		Master:           p.master(),
		Builder:          p.builder(),
		BuildNumber:      p.buildNumber(),
		BuildSchedMsec:   timeToMsec(p.buildScheduledTime()),
		StepName:         st.Name,
		StepText:         strings.Join(st.Text, "\n"),
		StepNumber:       0, // Will be populated by caller.
		HostName:         p.hostname(),
		Result:           getStepLegacyResultEnum(st),
		StepStartedMsec:  timeToMsec(stepStarted),
		StepDurationS:    float64(stepDuration.Seconds()),
		PatchUrl:         p.patchURL(),
		Project:          "",
		BbucketId:        p.bbInfo.Build.ID,
		BbucketUserAgent: p.bbInfo.Tag("user_agent"),

		BuildId:      p.buildID(),
		StepStarted:  stepStarted,
		StepFinished: stepFinished,
	}

	return &event, nil
}

func (m *Monitoring) forEachStep(fn func(*milo.Step)) {
	if m.result.Annotations == nil {
		return
	}

	var processStep func(st *milo.Step)
	processStep = func(st *milo.Step) {
		fn(st)
		for _, substep := range st.Substep {
			if sst := substep.GetStep(); sst != nil {
				processStep(sst)
			}
		}
	}

	processStep(m.result.Annotations)
}

func getStepLegacyResultEnum(st *milo.Step) string {
	if st == nil {
		return buildevent.ResultUnknown
	}

	// event.Result
	switch st.Status {
	case milo.Status_SUCCESS:
		return buildevent.ResultSuccess
	case milo.Status_FAILURE:
		if fd := st.FailureDetails; fd != nil {
			switch fd.Type {
			case milo.FailureDetails_INFRA:
				return buildevent.ResultInfraFailure
			default:
				return buildevent.ResultFailure
			}
		} else {
			return buildevent.ResultFailure
		}

	default:
		return buildevent.ResultUnknown
	}
}

type commonMonitoringParams struct {
	environ        map[string]string
	propertiesJSON map[string]string

	bbInfo buildBucketInfo
}

func (p *commonMonitoringParams) property(k string, v interface{}) bool {
	jsonValue := p.propertiesJSON[k]
	if jsonValue == "" {
		return false
	}

	if err := json.NewDecoder(strings.NewReader(jsonValue)).Decode(v); err == nil {
		return true
	}
	return false
}

// stringProperty attempts to decode a "propertiesJSON" value as a string. If
// it fails, an empty string will be returned.
func (p *commonMonitoringParams) stringProperty(k string) (v string) {
	p.property(k, &v)
	return
}

// numberProperty attempts to decode a "propertiesJSON" value as an int64. If
// it fails, 0 will be returned.
func (p *commonMonitoringParams) numberProperty(k string) (v int64) {
	p.property(k, &v)
	return
}

func (p *commonMonitoringParams) hostname() string   { return p.stringProperty("bot_id") }
func (p *commonMonitoringParams) master() string     { return p.stringProperty("mastername") }
func (p *commonMonitoringParams) builder() string    { return p.stringProperty("buildername") }
func (p *commonMonitoringParams) buildNumber() int64 { return p.numberProperty("buildnumber") }

func (p *commonMonitoringParams) buildScheduledTime() time.Time { return p.bbInfo.CreatedTime().UTC() }

func (p *commonMonitoringParams) patchURL() string {
	// Generate our patch URL.
	switch p.stringProperty("patch_storage") {
	case "gerrit":
		return fmt.Sprintf("%s/c/%d/%s",
			p.stringProperty("patch_gerrit_url"), p.numberProperty("patch_issue"), p.stringProperty("patch_set"))
	default:
		return ""
	}
}

func (p *commonMonitoringParams) swarmingHost() string {
	if v := p.environ["SWARMING_SERVER"]; v != "" {
		if u, err := url.Parse(v); err == nil {
			return u.Host
		}
	}
	return ""
}

func (p *commonMonitoringParams) swarmingRunID() string { return p.environ["SWARMING_TASK_ID"] }

// buildID generates a build ID.
//
// Currently, we will try and use the BuildBucket ID. If none of our
// uniqueness parameters geneate a build ID, we will not create one.
func (p *commonMonitoringParams) buildID() string {
	switch {
	case p.bbInfo.Hostname != "" && p.bbInfo.Build.ID != "":
		return fmt.Sprintf("buildbucket/%s/%s", p.bbInfo.Hostname, p.bbInfo.Build.ID)
	case p.swarmingHost() != "" && p.swarmingRunID() != "":
		return fmt.Sprintf("swarming/%s/%s", p.swarmingHost(), p.swarmingRunID())
	default:
		return ""
	}
}

type buildBucketInfoBuild struct {
	Bucket    string   `json:"bucket"`
	CreatedTS int64    `json:"created_ts"`
	ID        string   `json:"id"`
	Tags      []string `json:"tags"`
}

type buildBucketInfo struct {
	Hostname string               `json:"hostname"`
	Build    buildBucketInfoBuild `json:"build"`
}

func (bb *buildBucketInfo) Decode(v string) {
	_ = json.Unmarshal([]byte(v), bb)
}

// CreatedTime returns the time when a build was created.
//
// If that information is missing or zero, a zero-value Time will be returned.
func (bb *buildBucketInfo) CreatedTime() time.Time {
	if bb.Build.CreatedTS == 0 {
		return time.Time{}
	}

	// "created_ts" is in microseconds. To generate a UNIX time, we need to split
	// it into a seconds and nanoseconds component. "secs" will get the most
	// significant part of the value, and "nsecs" will hold the remainder.
	const microsecondsInASecond = int64(time.Second / time.Microsecond)
	const nanosecondsInAMicrosecond = int64(time.Microsecond / time.Nanosecond)
	secs := bb.Build.CreatedTS / microsecondsInASecond
	nsecs := (bb.Build.CreatedTS % microsecondsInASecond) * nanosecondsInAMicrosecond
	return time.Unix(secs, nsecs)
}

func (bb *buildBucketInfo) Tag(k string) string {
	for _, ent := range bb.Build.Tags {
		parts := strings.SplitN(ent, ":", 2)
		switch {
		case parts[0] != k:
			continue
		case len(parts) == 1:
			return ""
		default:
			return parts[1]
		}
	}
	return ""
}

// timeToMsec converts a Time into a count of milliseconds since UNIX epoch.
//
// If v is zero-value, timeToMsec will return 0.
func timeToMsec(v time.Time) int64 {
	if v.IsZero() {
		return 0
	}

	const nanosecondsInAMillisecond = int64(time.Millisecond / time.Nanosecond)
	return v.UnixNano() / nanosecondsInAMillisecond
}
