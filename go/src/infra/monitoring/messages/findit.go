// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package messages

// TODO(crbug.com/973577): remove all logic and messages for the old Findit/SoM
// API when all Findit analyses are migrated to v2.

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
	RevertCommitted  bool   `json:"revert_committed"`
}

// FinditResultV2 is the result of request to the findit server using
// buildbucket concepts.
// INTERNAL ONLY: For documentation of data format and fields, please check: https://docs.google.com/a/google.com/document/d/1u2O9iGroKKpL38SSK2E_krK29P5PeFI9fM_hgFkjGRc/edit?usp=sharing
type FinditResultV2 struct {
	BuildID            int64                   `json:"build_id"`
	BuildAlternativeID BuildIdentifierByNumber `json:"build_alternative_id"`
	StepName           string                  `json:"step_name"`
	TestName           string                  `json:"test_name"`
	LastPassedCommit   GitilesCommit           `json:"last_passed_commit"`
	FirstFailedCommit  GitilesCommit           `json:"first_failed_commit"`
	Culprits           []Culprit               `json:"culprits"`
	IsFinished         bool                    `json:"is_finished"`
	IsSupported        bool                    `json:"is_supported"`
	IsFlakyTest        bool                    `json:"is_flaky_test"`
	Markdown           string                  `json:"markdown"`
}

// BuildIdentifierByNumber is the alternative way to identify a LUCI build.
type BuildIdentifierByNumber struct {
	Project string `json:"project"`
	Bucket  string `json:"bucket"`
	Builder string `json:"builder"`
	Number  int64  `json:"number"`
}

// GitilesCommit is information about a gitiles commit.
type GitilesCommit struct {
	Host           string `json:"host"`
	Project        string `json:"project"`
	ID             string `json:"id"`
	Ref            string `json:"ref"`
	CommitPosition int    `json:"commit_position"`
}

// GerritChange is information about a gerrit change.
type GerritChange struct {
	Host     string `json:"host"`
	Project  string `json:"project"`
	Change   int64  `json:"change"`
	Patchset int64  `json:"patchset"`
	IsLanded bool   `json:"is_landed"`
}

// Culprit is a CL which is suspected to have caused a failure.
type Culprit struct {
	Commit   GitilesCommit `json:"commit"`
	Revert   GerritChange  `json:"revert"`
	Markdown string        `json:"markdown"`
}
