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
	runKey := workflowRunKey(c, runID)
	query := ds.NewQuery("FunctionRun").Ancestor(runKey)
	var functionRuns []*FunctionRun
	if err := ds.GetAll(c, query, &functionRuns); err != nil {
		return nil, err
	}
	return functionRuns, nil
}

// FetchComments returns a slice of all Comments for a run.
func FetchComments(c context.Context, runID int64) ([]*Comment, error) {
	runKey := workflowRunKey(c, runID)
	query := ds.NewQuery("Comment").Ancestor(runKey)
	var comments []*Comment
	if err := ds.GetAll(c, query, &comments); err != nil {
		return nil, err
	}
	return comments, nil
}

func workflowRunKey(c context.Context, runID int64) *ds.Key {
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", runID, nil)
	return ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
}
