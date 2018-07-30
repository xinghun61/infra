// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"strconv"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Progress implements Tricium.Progress.
func (r *TriciumServer) Progress(c context.Context, req *tricium.ProgressRequest) (res *tricium.ProgressResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	runID, err := validateProgressRequest(c, req)
	logging.Fields{
		"run ID": runID,
	}.Infof(c, "[frontend] Progress request received.")

	if err != nil {
		return nil, err
	}
	runState, functionProgress, err := progress(c, runID)
	if err != nil {
		return nil, err
	}
	return &tricium.ProgressResponse{
		RunId:            strconv.FormatInt(runID, 10),
		State:            runState,
		FunctionProgress: functionProgress,
	}, nil
}

// validateProgressRequest both validates the request and parses out the run ID.
//
// If the request is valid, it returns a run ID and nil; if invalid, it returns
// zero and a grpc error.
func validateProgressRequest(c context.Context, req *tricium.ProgressRequest) (int64, error) {
	switch source := req.Source.(type) {
	case *tricium.ProgressRequest_GerritRevision:
		if req.RunId != "" {
			// Either Gerrit details or run ID should be given; if both are
			// given then they may be conflicting; if the run ID is given
			// then there should be no need to specify Gerrit details.
			return 0, errors.Reason("both Gerrit details and run ID given").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		gr := source.GerritRevision
		if gr.Host == "" {
			return 0, errors.Reason("missing Gerrit host").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		if gr.Project == "" {
			return 0, errors.Reason("missing Gerrit project").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		if gr.Change == "" {
			// TODO(qyearsley): Validate change ID here as in analyze request.
			return 0, errors.Reason("missing Gerrit change ID").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		if gr.GitRef == "" {
			return 0, errors.Reason("missing Gerrit git ref").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		// Look up the run ID with the provided Gerrit change details.
		g := &GerritChangeToRunID{
			ID: gerritMappingID(gr.Host, gr.Project, gr.Change, gr.GitRef),
		}
		if err := ds.Get(c, g); err != nil {
			if err == ds.ErrNoSuchEntity {
				logging.Fields{
					"gerrit mapping ID": g.ID,
				}.Infof(c, "No GerritChangeToRunID found in datastore.")
				return 0, errors.Reason("no run ID found for Gerrit change").
					Tag(grpcutil.NotFoundTag).Err()
			}
			return 0, errors.Annotate(err, "failed to fetch run ID").
				Tag(grpcutil.InternalTag).Err()
		}
		return g.RunID, nil
	case nil:
		if req.RunId == "" {
			return 0, errors.Reason("missing run ID").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		runID, err := strconv.ParseInt(req.RunId, 10, 64)
		if err != nil {
			return 0, errors.Annotate(err, "invalid run ID").
				Tag(grpcutil.InvalidArgumentTag).Err()
		}
		return runID, nil
	default:
		return 0, errors.Reason("unexpected source type").
			Tag(grpcutil.InvalidArgumentTag).Err()
	}
}

func progress(c context.Context, runID int64) (tricium.State, []*tricium.FunctionProgress, error) {
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", runID, nil)
	requestRes := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
	if err := ds.Get(c, requestRes); err != nil {
		return tricium.State_PENDING, nil,
			errors.Annotate(err, "failed to get AnalyzeRequestResult for run %d", runID).
				Tag(grpcutil.InvalidArgumentTag).Err()

	}
	workflowRun := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, workflowRun); err != nil {
		return tricium.State_PENDING, nil, errors.Annotate(err, "failed to get WorkflowRun").
			Tag(grpcutil.InternalTag).Err()
	}
	functions, err := track.FetchFunctionRuns(c, runID)
	if err != nil {
		return tricium.State_PENDING, nil, errors.Annotate(err, "failed to get FunctionRuns").
			Tag(grpcutil.InternalTag).Err()
	}
	var workerResults []*track.WorkerRunResult
	for _, function := range functions {
		functionKey := ds.KeyForObj(c, function)
		for _, workerName := range function.Workers {
			workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, functionKey)
			workerResults = append(workerResults, &track.WorkerRunResult{ID: 1, Parent: workerKey})
		}
	}
	logging.Debugf(c, "Reading worker results for %v.", workerResults)
	if err := ds.Get(c, workerResults); err != nil && err != ds.ErrNoSuchEntity {
		return tricium.State_PENDING, nil, errors.Annotate(err, "failed to get WorkerRunResults").
			Tag(grpcutil.InternalTag).Err()
	}
	res := []*tricium.FunctionProgress{}
	for _, wr := range workerResults {
		p := &tricium.FunctionProgress{
			Name:        wr.Function,
			Platform:    wr.Platform,
			State:       wr.State,
			NumComments: int32(wr.NumComments),
		}
		if len(wr.SwarmingTaskID) > 0 {
			p.SwarmingUrl = workflowRun.SwarmingServerURL
			p.SwarmingTaskId = wr.SwarmingTaskID
		}
		res = append(res, p)
	}
	// Monitor progress requests per project and run ID.
	request := &track.AnalyzeRequest{ID: runID}
	if err := ds.Get(c, request); err != nil {
		return requestRes.State, res, errors.Annotate(err, "failed to get AnalyzeRequest").
			Tag(grpcutil.InternalTag).Err()
	}
	progressRequestCount.Add(c, 1, request.Project, strconv.FormatInt(runID, 10))
	return requestRes.State, res, nil
}
