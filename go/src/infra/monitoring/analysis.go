// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"time"

	msgs "infra/monitoring/messages"
)

const (
	// StaleMasterThreshold is the maximum number of seconds elapsed before a master
	// triggers a "Stale Master Data" alert.
	StaleMasterThreshold = 10 * time.Minute
)

var (
	// Aliased for testing purposes.
	now = func() time.Time {
		return time.Now()
	}
)

// MasterAlerts returns one list of alerts for builders attached to the master, and one list of alerts
// about the master itself.
func MasterAlerts(url string, be *msgs.BuildExtract) ([]msgs.Alert, []msgs.Alert) {
	// TODO: Add the logic for filling out builderAlerts.

	return []msgs.Alert{}, staleMasterAlerts(url, be)
}

func staleMasterAlerts(url string, be *msgs.BuildExtract) []msgs.Alert {
	ret := []msgs.Alert{}

	// Copied logic from builder_msgs.
	// No created_timestamp should be a warning sign, no?
	if be.CreatedTimestamp == msgs.EpochTime(0) {
		return ret
	}

	elapsed := now().Sub(be.CreatedTimestamp.Time())
	if elapsed > StaleMasterThreshold {
		ret = append(ret, msgs.Alert{
			Key:      "", // TODO: Assign keys.
			Title:    "Stale Master Data",
			Body:     fmt.Sprintf("%s elapsed since last update.", elapsed),
			Severity: 0,
			Time:     msgs.TimeToEpochTime(now()),
			Links:    []msgs.Link{{"Master Url", url}},
			// No type or extension for now.
		})
	}
	if elapsed < 0 {
		// Add this to the alerts returned, rather than just log it?
		log.Errorf("Master %s timestamp is newer than current time (%s): %s old.", url, now(), elapsed)
	}

	return ret
}
