// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package alerts contains structs defined to implement the json format:
// https://docs.google.com/document/d/10MESGzRy9uAy3Y3-PxUcjiuF3BD3FGGmCNvCjqm3WQQ/preview

package messages

import (
	"log"
	"os"
	"time"
)

var (
	googLoc *time.Location
	errLog  = log.New(os.Stderr, "", log.Lshortfile|log.Ltime)
)

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

// Alerts is the top-level entity in alerts.json.
type Alerts struct {
	Alerts            []Alert                    `json:"alerts"`
	RevisionSummaries map[string]RevisionSummary `json:"revision_summaries"`
	Timestamp         EpochTime                  `json:"timestamp"`
}

// Alert represents a condition that should be examined by a human.
type Alert struct {
	Key       string    `json:"key"`
	Title     string    `json:"title"`
	Body      string    `json:"body"`
	Severity  int       `json:"severity"` // TODO: consider using an enum.
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

// Link can be attached to an alert to provide more context to the sheriff.
type Link struct {
	Title string `json:"title"`
	Href  string `json:"href"`
}

// BuildFailure is an Extension.
type BuildFailure struct {
	TreeCloser       bool              `json:"tree_closer"`
	Builders         []AlertedBuilder  `json:"builders"`
	Reasons          []Reason          `json:"reasons"`
	RegressionRanges []RegressionRange `json:"regression_ranges"`
	SuspectedCLs     []SuspectCL       `json:"suspected_cls"`
}

// AlertedBuilder represents an individual builder.
type AlertedBuilder struct {
	Name      string    `json:"name"`
	URL       string    `json:"url"`
	StartTime EpochTime `json:"start_time"`
	// FirstFailure is the build number of first failure.
	FirstFailure int64 `json:"first_failure"`
	// LatestFailure is the build number of latest failure.
	LatestFailure int64 `json:"latest_failure"`
}

// Reason contains information about why the Alert was triggered.
type Reason struct {
	// Could be more detailed about test failures. For instance, we could
	// indicate expected vs. actual result.
	TestNames []string `json:"test_names"`
	Step      string   `json:"step"`
	URL       string   `json:"url"`
}

// RegressionRange identifies the bounds of the location of a regression.
type RegressionRange struct {
	Repo      string   `json:"repo"`
	URL       string   `json:"url"`
	Revisions []string `json:"revisions"`
	Positions []string `json:"positions"`
}

// RevisionSummary summarizes some information about a revision.
type RevisionSummary struct {
	GitHash     string    `json:"git_hash"`
	Position    string    `json:"commit_position"`
	Branch      string    `json:"branch"`
	Link        string    `json:"link"`
	Description string    `json:"description"`
	Author      string    `json:"author"`
	When        EpochTime `json:"when"`
}
