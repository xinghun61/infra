// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// These structs are for parsing test-results.appspot.com responses.

package messages

// TestResults represents the uploaded results of a set of tests for a build.
type TestResults struct {
	BuildNumber       string `json:"build_number"`
	SecondsSinceEpoch int64  `json:"seconds_since_epoch"`
	// Tests is an arbitrarily nested tree of test names
	Tests map[string]interface{} `json:"tests"`
}

// TestResult represents the output of an individual test.
type TestResult struct {
	Expected string
	Actual   string
	Time     int64
}
