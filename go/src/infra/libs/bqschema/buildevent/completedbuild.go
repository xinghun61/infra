// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildevent

const (
	// ResultUnknown and associated Result* values are suitable for the "Result"
	// enum field in LegacyCompletedBuilds and LegacyBuildEvents.
	ResultUnknown = ""
	// ResultSuccess is a successful build result.
	ResultSuccess = "SUCCESS"
	// ResultFailure is a failed build result.
	ResultFailure = "FAILURE"
	// ResultInfraFailure is a failed build result attributed to infrastructure.
	ResultInfraFailure = "INFRA_FAILURE"
	// ResultWarning is a successful build result with a noted warning.
	ResultWarning = "WARNING"
	// ResultSkipped indicates that the build was not executed.
	ResultSkipped = "SKIPPED"
	// ResultRetry indicates that a build should be retried.
	ResultRetry = "RETRY"
)

const (
	// CategoryUnknown and associated Category* values are suitable for the
	// "Category" enum field in LegacyCompletedBuilds.
	CategoryUnknown = ""
	// CategoryCQ is a scheduling category for the commit queue.
	CategoryCQ = "CQ"
	// CategoryCQExperimental is a scheduling category for an experimental commit
	// queue.
	CategoryCQExperimental = "CQ_EXPERIMENTAL"
	// CategoryGitCLTry is a scheduling category for the "git cl try" command.
	CategoryGitCLTry = "GIT_CL_TRY"
)
