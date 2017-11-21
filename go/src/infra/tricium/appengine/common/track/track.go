// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package track implements shared tracking functionality for the Tricium service modules.
//
// Overview diagram:
//
//    +-----------------+
//    |AnalyzeRequest   |
//    |id=<generated_id>|
//    +---+-------------+
//        |
//        +----------------------+
//        |                      |
//    +---+----------------+ +---+-------+
//    |AnalyzeRequestResult| |WorkflowRun|
//    |id=1                | |id=1       |
//    +---+----------------+ +-----------+
//                               |
//                               +----------------------+
//                               |                      |
//                           +---+-------------+ +---+-------------+
//                           |WorkflowRunResult| |AnalyzerRun      |
//                           |id=1             | |id=<analyzerName>|
//                           +-----------------+ +---+-------------+
//                                                   |
//                               +-------------------+
//                               |                   |
//                           +---+-------------+ +---+----------------------+
//                           |AnalyzerRunResult| |WorkerRun                 |
//                           |id=1             | |id=<analyzerName_platform>|
//                           +-----------------+ +---+----------------------+
//                                                   |
//                                          +--------+---------+
//                                          |                  |
//                                      +---+-----------+ +----+------------+
//                                      |WorkerRunResult| |Comment          |
//                                      |id=1           | |id=<generated_id>|
//                                      +---------------+ +----+------------+
//                                                             |
//                                          +------------------+
//                                          |                  |
//                                       +--+-------------+ +--+------------+
//                                       |CommentSelection| |CommentFeedback|
//                                       |id=1            | |id=1           |
//                                       +-----------   --+ +---------------+
//
package track

import (
	"fmt"
	"strings"
	"time"

	ds "go.chromium.org/gae/service/datastore"

	"infra/tricium/api/v1"
)

// AnalyzeRequest represents one Tricium Analyze RPC request.
//
// Immutable root entry.
type AnalyzeRequest struct {
	// LUCI datastore ID field with generated value.
	ID int64 `gae:"$id"`
	// Time when the corresponding request was received, time recorded in the reporter.
	Received time.Time
	// The Tricium project of the request.
	// This is the project name listed in the Tricium service config.
	Project string
	// File paths listed in the request.
	Paths []string `gae:",noindex"`
	// Git repository hosting files in the request.
	GitRepo string `gae:",noindex"`
	// Git ref to use in the Git repo.
	GitRef string `gae:",noindex"`
	// Consumer of progress updates and results.
	Consumer tricium.Consumer
	// Gerrit details for when the Gerrit reporter is selected.
	GerritHost    string `gae:",noindex"`
	GerritProject string `gae:",noindex"`
	GerritChange  string `gae:",noindex"`
	// Note that Gerrit revision is another name for Gerrit patch set.
	GerritRevision string `gae:",noindex"`
}

// AnalyzeRequestResult tracks the state of a tricium.Analyze request.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to AnalyzeRequest entity) fields.
type AnalyzeRequestResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// State of the Analyze request; running, success, or failure.
	State tricium.State
}

// WorkflowRun declares a request to execute a Tricium workflow.
//
// Immutable root of the complete workflow execution.
// LUCI datastore ID (=1) and parent (=key to AnalyzeRequest entity) fields.
type WorkflowRun struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of analyzers included in this workflow.
	//
	// Included here to allow for direct access without queries.
	Analyzers []string `gae:",noindex"`
	// Isolate server URL.
	IsolateServerURL string `gae:",noindex"`
	// Swarming server URL.
	SwarmingServerURL string `gae:",noindex"`
}

// WorkflowRunResult tracks the state of a workflow run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to WorkflowRun entity) fields.
type WorkflowRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// State of the parent request; running, success, or failure.
	//
	// This state is an aggregation of the run state of triggered analyzers.
	State tricium.State
	// Number of comments produced for this analyzer.
	// If results were merged, then this is the merged number of results.
	NumComments int
	// If the results for this analyzer were merged.
	HasMergedResults bool
}

// AnalyzerRun declares a request to execute an analyzer.
//
// Immutable entity.
// LUCI datastore ID (="AnalyzerName") and parent (=key to WorkflowRun entity) fields.
type AnalyzerRun struct {
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of workers launched for this analyzer.
	//
	// Included here to allow for direct access without queries.
	Workers []string `gae:",noindex"`
}

// AnalyzerRunResult tracks the state of an analyzer run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to AnalyzerRun entity) fields.
type AnalyzerRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of analyzer.
	//
	// Added here in addition to in the parent key for indexing.
	Name string
	// State of the parent analyzer run; running, success, or failure.
	//
	// This state is an aggregation of the run state of triggered analyzer workers.
	State tricium.State

	// Number of comments produced for this analyzer.
	//
	// If results were merged, then this is the merged number of results.
	NumComments int

	// If the results for this analyzer were merged.
	HasMergedResults bool
}

// WorkerRun declare a request to execute an analyzer worker.
//
// Immutable entity.
// LUCI datastore ID (="WorkerName") and parent (=key to AnalyzerRun entity) fields.
type WorkerRun struct {
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Platform this worker is producing results for.
	Platform tricium.Platform_Name
	// Names of workers succeeding this worker in the workflow.
	Next []string `gae:",noindex"`
}

// WorkerRunResult tracks the state of a worker run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to WorkerRun entity) fields.
type WorkerRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of worker.
	//
	// Stored here, in addition to in the parent ID, for indexing
	// and convenience.
	Name string
	// Analyzer this worker is running.
	//
	// Stored here, in addition to in the ID of ancestors, for indexing
	// and convenience.
	Analyzer string
	// Platform this worker is running on.
	Platform tricium.Platform_Name
	// State of the parent worker run; running, success, or failure.
	State tricium.State
	// Hash to the isolated input provided to the corresponding swarming task.
	IsolatedInput string `gae:",noindex"`
	// Hash to the isolated output collected from the corresponding swarming task.
	IsolatedOutput string `gae:",noindex"`
	SwarmingTaskID string `gae:",noindex"`
	// Exit code of the corresponding swarming task.
	ExitCode int
	// Number of comments produced by this worker.
	NumComments int `gae:",noindex"`
	// Tricium result encoded as JSON.
	Result string `gae:",noindex"`
}

// Comment tracks a comment generated by a worker.
//
// Immutable entity.
// LUCI datastore ID (=generated) and parent (=key to WorkerRun entity) fields.
type Comment struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Comment encoded as JSON.
	//
	// The comment must be an encoded tricium.Data_Comment JSON message
	// TODO(emso): Consider storing structured comment data.
	Comment []byte `gae:",noindex"`
	// Comment category with subcategories.
	//
	// This includes the analyzer name, e.g., "clang-tidy/llvm-header-guard".
	Category string
	// Platforms this comment applies to.
	//
	// This is a int64 bit map using the tricium.Platform_Name number values for platforms.
	Platforms int64
}

// CommentSelection tracks selection of comments.
//
// When an analyzer has several workers running the analyzer using different configurations
// the resulting comments are merged to avoid duplication of results for users.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to Comment entity) fields.
type CommentSelection struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Whether this comments was included in the overall result of the enclosing request.
	//
	// All comments are included by default, but comments may need to be merged
	// in the case when comments for a category are produced for multiple platforms.
	Included bool
}

// CommentFeedback tracks 'not useful' user feedback for a comment.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to Comment entity) fields.
type CommentFeedback struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Number of 'not useful' clicks.
	NotUseful int
	// Links to more information about why the comment was found not useful.
	//
	// This should typically be a link to a Monorail issue.
	NotUsefulIssueURL []string
	// TODO(emso): Collect data for number of times shown?
}

const workerSeparator = "_"

// ExtractAnalyzerPlatform extracts the analyzer and platform name from a worker name.
//
// The worker name must be on the form 'AnalyzerName_PLATFORM'.
func ExtractAnalyzerPlatform(workerName string) (string, string, error) {
	parts := strings.SplitN(workerName, workerSeparator, 2)
	if len(parts) != 2 {
		return "", "", fmt.Errorf("malformed worker name: %s", workerName)
	}
	return parts[0], parts[1], nil

}
