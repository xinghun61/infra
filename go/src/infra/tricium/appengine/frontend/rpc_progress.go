// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Progress implements Tricium.Progress.
func (r *TriciumServer) Progress(c context.Context, req *tricium.ProgressRequest) (*tricium.ProgressResponse, error) {
	runID, err := validateProgressRequest(c, req)
	if err != nil {
		return nil, err
	}
	runState, functionProgress, errCode, err := progress(c, runID)
	if err != nil {
		logging.WithError(err).Errorf(c, "progress failed, run ID: %d", runID)
		return nil, grpc.Errorf(errCode, "failed to execute progress request")
	}
	logging.Infof(c, "[frontend] Function progress: %v", functionProgress)
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
			return 0, grpc.Errorf(codes.InvalidArgument, "both Gerrit details and run ID given")
		}
		gr := source.GerritRevision
		if gr.Host == "" {
			return 0, grpc.Errorf(codes.InvalidArgument, "missing Gerrit host")
		}
		if gr.Project == "" {
			return 0, grpc.Errorf(codes.InvalidArgument, "missing Gerrit project")
		}
		if gr.Change == "" {
			// TODO(qyearsley): Validate change ID here as in analyze request.
			return 0, grpc.Errorf(codes.InvalidArgument, "missing Gerrit change ID")
		}
		if gr.GitRef == "" {
			return 0, grpc.Errorf(codes.InvalidArgument, "missing Gerrit git ref")
		}
		// Look up the run ID with the provided Gerrit change details.
		g := &GerritChangeToRunID{
			ID: gerritMappingID(gr.Host, gr.Project, gr.Change, gr.GitRef),
		}
		if err := ds.Get(c, g); err != nil {
			if err == ds.ErrNoSuchEntity {
				logging.Fields{
					"gerrit mapping ID": g.ID,
				}.Infof(c, "No GerritChangeToRunID found in datastore")
				return 0, grpc.Errorf(codes.NotFound, "no run ID found")
			}
			logging.WithError(err).Errorf(c, "Failed to fetch GerritChangeToRunID entity")
			return 0, grpc.Errorf(codes.Internal, "failed to fetch run ID")
		}
		return g.RunID, nil
	case nil:
		// Run ID may be specified.
		if req.RunId == "" {
			return 0, grpc.Errorf(codes.InvalidArgument, "missing run ID")
		}
		runID, err := strconv.ParseInt(req.RunId, 10, 64)
		if err != nil {
			logging.WithError(err).Errorf(c, "failed to parse run ID: %s", req.RunId)
			return 0, grpc.Errorf(codes.InvalidArgument, "invalid run ID")
		}
		return runID, nil
	default:
		return 0, grpc.Errorf(codes.InvalidArgument, "unexpected source type")
	}
}

func progress(c context.Context, runID int64) (tricium.State, []*tricium.FunctionProgress, codes.Code, error) {
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", runID, nil)
	requestRes := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
	if err := ds.Get(c, requestRes); err != nil {
		return tricium.State_PENDING, nil, codes.InvalidArgument, fmt.Errorf("failed to get AnalyzeRequestResult: %v", err)
	}
	workflowRun := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, workflowRun); err != nil {
		return tricium.State_PENDING, nil, codes.Internal, fmt.Errorf("failed to get WorkflowRun: %v", err)
	}
	functions, err := track.FetchFunctionRuns(c, runID)
	if err != nil {
		return tricium.State_PENDING, nil, codes.Internal, fmt.Errorf("failed to get FunctionRun entities: %v", err)
	}
	var workerResults []*track.WorkerRunResult
	for _, function := range functions {
		functionKey := ds.KeyForObj(c, function)
		for _, workerName := range function.Workers {
			workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, functionKey)
			workerResults = append(workerResults, &track.WorkerRunResult{ID: 1, Parent: workerKey})
		}
	}
	logging.Debugf(c, "Reading worker results for %v", workerResults)
	if err := ds.Get(c, workerResults); err != nil && err != ds.ErrNoSuchEntity {
		return tricium.State_PENDING, nil, codes.Internal, fmt.Errorf("failed to get WorkerRunResult entities: %v", err)
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
		return requestRes.State, res, codes.Internal, fmt.Errorf("failed to get AnalyzeRequest: %v", err)
	}
	progressRequestCount.Add(c, 1, request.Project, strconv.FormatInt(runID, 10))
	return requestRes.State, res, codes.OK, nil
}
