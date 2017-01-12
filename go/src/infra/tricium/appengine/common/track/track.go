// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package track implements shared tracking functionality for the Tricium service modules.
package track

import (
	"time"

	ds "github.com/luci/gae/service/datastore"
)

// Run tracks the processing of one analysis request.
type Run struct {
	// LUCI datastore fields.
	ID int64 `gae:"$id"`
	// Time when the corresponding request was received, time recorded in the reporter.
	Received time.Time
	// State of this run; received, launched, or done-*, with done indicating success.
	State RunState
}

// ServiceRequest lists the fields included in a request to the Tricium service.
//
// Stored with 'Run' as parent and is read-only.
type ServiceRequest struct {
	// LUCI datastore fields.
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Tricium connected project receiving the request.
	Project string
	// File paths listed in the request.
	Paths []string `gae:",noindex"`
	// Git repository hosting files in the request.
	GitRepo string `gae:",noindex"`
	// Git ref to use in the Git repo.
	GitRef string `gae:",noindex"`
}

// RunState specifies the state of a run, analyzer, or worker.
type RunState int8

const (
	// Pending is for when an analysis request has been received.
	Pending RunState = iota + 1
	// Launched is for when the workflow of a request has been launched.
	Launched
	// DoneSuccess is for when a workflow, analyzer, or worker has successfully completed.
	DoneSuccess
	// DoneFailure is for when a workflow, analyzer, or worker has completed with failure.
	// For an analyzer or workflow, this state is aggregated from underlying worker or analyzers.
	// A worker is considered to have completed with failure if it has produced results, when
	// those results are comments.
	DoneFailure
	// DoneException is for when a workflow, analyzer, or worker has completed with an exception.
	// Any non-zero exit code of a worker is considered an exception.
	// For an analyzer or workflow, this state is aggregated from underying workers or analyzers.
	DoneException
)

// IsDone returns true is state is done regardless the kind of done state.
func (r RunState) IsDone() bool {
	return r == DoneSuccess || r == DoneFailure || r == DoneException
}

// AnalyzerInvocation tracks the execution of an analyzer.
//
// This may happen in one or more worker invocations, each running on different platforms.
// Stored with 'Run' as parent.
type AnalyzerInvocation struct {
	// LUCI datastore fields.
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of the analyzer. The workflow for a run may have several
	// workers for one analyzer, each running on different platforms.
	Name string
	// State of this analyzer run; launched, or done-*, with done indicating success.
	// This state is an aggregation of the run state of analyzer workers.
	State RunState
}

// WorkerInvocation tracks the execution of a worker.
//
// Stored with 'AnalyzerInvocation' as parent.
type WorkerInvocation struct {
	// LUCI datastore fields.
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of the worker. Same as that used in the workflow configuration.
	Name string
	// State of this worker run; launched, or done-*, with done indicating success.
	State RunState
	// Name of the platform configuration used for the swarming task of this worker.
	Platform string
	// Hash to the isolated input provided to the corresponding swarming task.
	IsolatedInput string `gae:",noindex"`
	// Hash to the isolated output collected from the corresponding swarming task.
	IsolatedOutput string `gae:",noindex"`
	// Names of workers succeeding this worker in the workflow.
	Next []string `gae:",noindex"`
	//  Exit code of the corresponding swarming task.
	ExitCode int
	// Swarming server URL.
	SwarmingURL string `gae:",noindex"`
	// Swarming task ID.
	TaskID string `gae:",noindex"`
}
