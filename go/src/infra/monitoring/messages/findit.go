// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package messages

// FinditResult is the result of request to the findit server.
// INTERNAL ONLY: For documentation of data format and fields, please check: https://docs.google.com/a/google.com/document/d/1u2O9iGroKKpL38SSK2E_krK29P5PeFI9fM_hgFkjGRc/edit?usp=sharing
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
	TryJobStatus                string      `json:"try_job_status"`
	IsFlakyTest                 bool        `json:"is_flaky_test"`
	HasFindings                 bool        `json:"has_findings"`
	IsFinished                  bool        `json:"is_finished"`
	IsSupported                 bool        `json:"is_supported"`
}

// SuspectCL is a CL which is suspected to have caused a failure.
type SuspectCL struct {
	RepoName         string `json:"repo_name"`
	Revision         string `json:"revision"`
	CommitPosition   int64  `json:"commit_position,omitempty"`
	Confidence       int    `json:"confidence"`
	AnalysisApproach string `json:"analysis_approach"`
	RevertCLURL      string `json:"revert_cl_url"`
}
