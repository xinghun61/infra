// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package alerts contains structs defined to implement the json format:
// https://docs.google.com/document/d/10MESGzRy9uAy3Y3-PxUcjiuF3BD3FGGmCNvCjqm3WQQ/preview

package messages

import (
	"encoding/json"
	"log"
	"os"
	"time"
)

var (
	googLoc *time.Location
	errLog  = log.New(os.Stderr, "", log.Lshortfile|log.Ltime)
)

// AlertType is a type of alert; used for categorizing and grouping alerts on
// the SOM frontend.
type AlertType string

const (
	// GoogleTimeZone is the timezone used by the services whose
	// messages this package parses.
	GoogleTimeZone = "UTC"

	// AlertStaleMaster indicates that we have no recent updates from the master.
	AlertStaleMaster = "stale-master"

	// AlertHungBuilder indicates that a builder has been executing a step for too long.
	AlertHungBuilder = "hung-builder"

	// AlertOfflineBuilder indicates that we have no recent updates from the builder.
	AlertOfflineBuilder = "offline-builder"

	// AlertIdleBuilder indicates that a builder has not executed any builds recently
	// even though it has requests queued up.
	AlertIdleBuilder = "idle-builder"

	// AlertInfraFailure indicates that a builder step failed due to infrastructure
	// problems rather than errors in the code it tried to build or execute.
	AlertInfraFailure = "infra-failure"

	// AlertBuildFailure indicates that one of the build steps failed, must likely
	// due to the patch it's building/running with.
	AlertBuildFailure = "build-failure"
)

func init() {
	var err error
	googLoc, err = time.LoadLocation(GoogleTimeZone)
	if err != nil {
		errLog.Printf("Could not load Google Time Zone (%s)", GoogleTimeZone)
		os.Exit(1)
	}
}

// EpochTime is used for marshalling timestamps represented as doubles in json.
type EpochTime float64

// Time returns a time.Time value corresponding to the json value.
func (j EpochTime) Time() time.Time {
	return time.Unix(int64(j), 0).In(googLoc)
}

// TimeToEpochTime converts a time.Time value to a EpochTime value.
func TimeToEpochTime(t time.Time) EpochTime {
	return EpochTime(t.Unix())
}

// AlertsSummary is the top-level entity in alerts.json.
type AlertsSummary struct {
	Alerts            []Alert                    `json:"alerts"`
	Resolved          []Alert                    `json:"resolved"`
	RevisionSummaries map[string]RevisionSummary `json:"revision_summaries"`
	Timestamp         EpochTime                  `json:"timestamp"`
}

// Severity is a sorted order of how severe an alert is.
type Severity int

const (
	// TreeCloser is an alert which closes the tree. Highest priority alert.
	TreeCloser Severity = iota
	// StaleMaster is an alert about stale master data.
	StaleMaster
	// HungBuilder is an alert about a builder being hung (stuck running a particular step)
	HungBuilder
	// InfraFailure is an infrastructure failure. It is higher severity than a reliable failure
	// because if there is an infrastructure failure, the test code is not even run,
	// and so we are losing data about if the tests pass or not.
	InfraFailure
	// ReliableFailure is a failure which has shown up multiple times.
	ReliableFailure
	// NewFailure is a failure which just started happening.
	NewFailure
	// IdleBuilder is a builder which is "idle" (buildbot term) and which has above
	// a certain threshold of pending builds.
	IdleBuilder
	// OfflineBuilder is a builder which is offline.
	OfflineBuilder
	// NoSeverity is a placeholder Severity value which means nothing. Used by analysis
	// to indicate that it doesn't have a particular Severity to assign to an alert.
	NoSeverity
)

// Alert represents a condition that should be examined by a human.
type Alert struct {
	Key       string    `json:"key"`
	Title     string    `json:"title"`
	Body      string    `json:"body"`
	Severity  Severity  `json:"severity"` // TODO: consider using an enum.
	Time      EpochTime `json:"time"`
	StartTime EpochTime `json:"start_time"`
	Links     []Link    `json:"links"`
	Tags      []string  `json:"tags"`
	// Type determines what kind of extension has been set on the Alert.
	Type AlertType `json:"type"`
	// Extension may take on different concrete types depending on the
	// code that generates the Alert.
	Extension interface{} `json:"extension"`
}

// Alerts is a slice of alerts, sorted by Key by default
type Alerts []Alert

func (a Alerts) Len() int      { return len(a) }
func (a Alerts) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a Alerts) Less(i, j int) bool {
	return a[i].Key < a[j].Key
}

// Link can be attached to an alert to provide more context to the sheriff.
type Link struct {
	Title string `json:"title"`
	Href  string `json:"href"`
}

// BuildFailure is an Extension.
type BuildFailure struct {
	TreeCloser       bool               `json:"tree_closer"`
	Builders         []AlertedBuilder   `json:"builders"`
	StepAtFault      *BuildStep         `json:"-"`
	Reason           *Reason            `json:"reason"`
	RegressionRanges []*RegressionRange `json:"regression_ranges"`
	SuspectedCLs     []SuspectCL        `json:"suspected_cls"`
	// Status of Findit analysis: RUNNING or FINISHED.
	FinditStatus string `json:"findit_status"`
	// Url to Findit result page.
	FinditURL   string `json:"findit_url"`
	HasFindings bool   `json:"has_findings"`
	IsFinished  bool   `json:"is_finished"`
	IsSupported bool   `json:"is_supported"`
}

// BuildStep is a step which was run in a particular build. Useful for analyzing
// and generating additional data for extensions.
type BuildStep struct {
	Master *MasterLocation
	Build  *Build
	Step   *Step
}

// Reason is the cause of a build extension failure.
type Reason struct {
	Raw ReasonRaw
}

// Signature is a unique identifier for reasons of the same Kind.
func (r *Reason) Signature() string {
	return r.Raw.Signature()
}

// Kind is the kind of the reason. Useful for categorization.
func (r *Reason) Kind() string {
	// FIXME: This is possibly duplicated with AlertType
	return r.Raw.Kind()
}

// Title returns a title a group of build steps should have, as an alert.
func (r *Reason) Title(bses []*BuildStep) string {
	return r.Raw.Title(bses)
}

// MarshalJSON returns the json marshalled version of the Reason. Delegates to
// the raw reason.
func (r *Reason) MarshalJSON() ([]byte, error) {
	return json.Marshal(r.Raw)
}

// ReasonRaw is the interface any results an analysis pipeline outputs must
// implement.
type ReasonRaw interface {
	Signature() string
	Kind() string
	Severity() Severity
	Title([]*BuildStep) string
}

// AlertedBuilder represents an individual builder.
type AlertedBuilder struct {
	Name      string    `json:"name"`
	Master    string    `json:"master"`
	URL       string    `json:"url"`
	StartTime EpochTime `json:"start_time"`
	// FirstFailure is the build number of first failure.
	FirstFailure int64 `json:"first_failure"`
	// LatestFailure is the build number of latest failure.
	LatestFailure int64 `json:"latest_failure"`
	// LatestPassing is the build number of latest passing build
	LatestPassing int64 `json:"latest_passing"`
	Count         int   `json:"count"`
}

// RegressionRange identifies the bounds of the location of a regression.
type RegressionRange struct {
	Repo string `json:"repo"`
	URL  string `json:"url"`
	// Revisions have the first and last revisions in the range,
	// And RevisionsWithResults have the revisions that are suspected.
	Revisions            []string                   `json:"revisions"`
	Positions            []string                   `json:"positions"`
	RevisionsWithResults []RevisionWithFinditResult `json:"revisions_with_results"`
}

// RevisionWithFinditResult saves information from Findit about a specific revision.
type RevisionWithFinditResult struct {
	Revision string `json:"revision"`

	// A flag to determine if Findit finds it to be a culprit to some failures.
	IsSuspect bool `json:"is_suspect"`

	// A score calculated by Findit based on historical triaging results of the same type of suspected CLs.
	// Only has value when IsSuspect is true.
	Confidence int `json:"confidence"`

	// Used to indicate how Findit finds this CL as a suspect.
	// Only has a [value when IsSuspect is true.
	AnalysisApproach string `json:"analysis_approach"`
}

// RevisionSummary summarizes some information about a revision.
type RevisionSummary struct {
	GitHash     string    `json:"git_hash"`
	Position    int       `json:"commit_position"`
	Branch      string    `json:"branch"`
	Link        string    `json:"link"`
	Description string    `json:"description"`
	Author      string    `json:"author"`
	When        EpochTime `json:"when"`
}
