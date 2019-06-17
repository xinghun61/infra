// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	"context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
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

// FetchRecentRequests returns a slice of AnalyzeRequest entities
// for the most recently received requests for projects readable
// to the current user.
func FetchRecentRequests(c context.Context, cp config.ProviderAPI) ([]*AnalyzeRequest, error) {
	var requests []*AnalyzeRequest
	// NB! This only lists the last 20 requests.
	q := ds.NewQuery("AnalyzeRequest").Order("-Received").Limit(20)
	if err := ds.GetAll(c, q, &requests); err != nil {
		logging.WithError(err).Errorf(c, "failed to get AnalyzeRequest entities")
		return nil, err
	}
	// Only include readable requests.
	checked := map[string]bool{}
	var rs []*AnalyzeRequest
	for _, r := range requests {
		if _, ok := checked[r.Project]; !ok {
			pc, err := cp.GetProjectConfig(c, r.Project)
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to get config for project %s", r.Project)
				return nil, err
			}
			checked[r.Project], err = tricium.CanRead(c, pc)
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to check read access %s", r.Project)
				return nil, err
			}
		}
		if checked[r.Project] {
			rs = append(rs, r)
		}
	}
	return rs, nil
}
