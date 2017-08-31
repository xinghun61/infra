// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package messages

// AlertTestResults holds the results of a failing test that caused an alert.
type AlertTestResults struct {
	TestName      string          `json:"test_name"`
	MasterResults []MasterResults `json:"master_results"`
}

// MasterResults holds the test results for one master.
type MasterResults struct {
	MasterName     string           `json:"master_name"`
	BuilderResults []BuilderResults `json:"builder_results"`
}

// BuilderResults holds the test results for one builder.
type BuilderResults struct {
	BuilderName   string    `json:"builder_name"`
	TotalFailures string    `json:"total_failures"`
	Results       []Results `json:"results"`
}

// Results holds the test result from one build.
type Results struct {
	BuildNumber int   `json:"build_number" bigquery:"build_number"`
	Actual      []int `json:"test_actual" bigquery:"actual"`
	Expected    []int `json:"test_expected" bigquery:"expected"`
}
