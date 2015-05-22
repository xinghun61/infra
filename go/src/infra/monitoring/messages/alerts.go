// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package alerts contains structs defined to implement the json format:
// https://docs.google.com/document/d/10MESGzRy9uAy3Y3-PxUcjiuF3BD3FGGmCNvCjqm3WQQ/preview

package messages

import (
	"os"
	"time"

	"infra/libs/logging/gologger"
)

var (
	googLoc *time.Location
	log     = gologger.Get()
)

const (
	// GoogleTimeZone is the timezone used by the services whose
	// messages this package parses.
	GoogleTimeZone = "UTC"
)

func init() {
	var err error
	googLoc, err = time.LoadLocation(GoogleTimeZone)
	if err != nil {
		log.Errorf("Could not load Google Time Zone (%s)", GoogleTimeZone)
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
	Alerts    []Alert
	Timestamp EpochTime
}

// Alert represents a condition that should be examined by a human.
type Alert struct {
	Key, Title, Body string
	Severity         int // TODO: consider using an enum.
	Time             EpochTime
	StartTime        EpochTime `json:"start_time"`
	Links            []Link
	Tags             []string
	// Type determines what kind of extension has been set on the Alert.
	Type string
	// Extension may take on different concrete types depending on the
	// code that generates the Alert.
	Extension interface{}
}

// Link can be attached to an alert to provide more context to the sheriff.
type Link struct {
	Title string
	Href  string
}

// BuildFailure is an Extension.
type BuildFailure struct {
	TreeCloser       bool
	Builders         []AlertedBuilder
	Reasons          []Reason
	RegressionRanges []RegressionRange `json:"regression_ranges"`
}

// AlertedBuilder represents an individual builder.
type AlertedBuilder struct {
	Name string
	URL  string
	// FirstFailure is the build number of first failure.
	FirstFailure int64 `json:"first_failure"`
	// LatestFailure is the build number of latest failure.
	LatestFailure int64 `json:"latest_failure"`
}

// Reason contains information about why the Alert was triggered.
type Reason struct {
	TestName string
	Step     string
	URL      string
}

// RegressionRange identifies the bounds of the location of a regression.
type RegressionRange struct {
	Repo      string
	URL       string
	Revisions []string
}
