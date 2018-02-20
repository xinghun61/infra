// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	ds "go.chromium.org/gae/service/datastore"

	"golang.org/x/net/context"
)

// FetchFunctionRuns returns a slice of all FunctionRuns for a run.
func FetchFunctionRuns(c context.Context, runID int64) ([]*FunctionRun, error) {
	var functionRuns []*FunctionRun
	query := queryForRunID(c, "FunctionRun", runID)
	err := ds.GetAll(c, query, &functionRuns)
	return functionRuns, err
}

// FetchWorkerRuns returns a slice of all WorkerRuns for a run.
func FetchWorkerRuns(c context.Context, runID int64) ([]*WorkerRun, error) {
	var workerRuns []*WorkerRun
	query := queryForRunID(c, "WorkerRun", runID)
	err := ds.GetAll(c, query, &workerRuns)
	return workerRuns, err
}

// FetchComments returns a slice of all Comments for a run.
func FetchComments(c context.Context, runID int64) ([]*Comment, error) {
	var comments []*Comment
	query := queryForRunID(c, "Comment", runID)
	err := ds.GetAll(c, query, &comments)
	return comments, err
}

func queryForRunID(c context.Context, kind string, runID int64) *ds.Query {
	return ds.NewQuery(kind).Ancestor(workflowRunKey(c, runID))
}

func workflowRunKey(c context.Context, runID int64) *ds.Key {
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", runID, nil)
	return ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
}
