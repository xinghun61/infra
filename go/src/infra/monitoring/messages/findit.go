// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package messages

// FinditResult is the result of request to the findit server.
type FinditResult struct {
	MasterURL                   string      `json:"master_url"`
	BuilderName                 string      `json:"builder_name"`
	BuildNumber                 int64       `json:"build_number"`
	StepName                    string      `json:"step_name"`
	IsSubTest                   bool        `json:"is_sub_test"`
	TestName                    string      `json:"test_name"`
	FirstKnownFailedBuildNumber int64       `json:"first_known_failed_build_number"`
	SuspectedCLs                []SuspectCL `json:"suspected_cls"`
	AnalysisApproach            string      `json:"analysis_approach"`
}

// SuspectCL is a CL which is suspected to have caused a failure.
type SuspectCL struct {
	RepoName       string `json:"repo_name"`
	Revision       string `json:"revision"`
	CommitPosition int64  `json:"commit_position,omitempty"`
}
