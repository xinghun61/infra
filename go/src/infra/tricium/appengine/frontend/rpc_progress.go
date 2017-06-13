// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Progress implements Tricium.Progress.
func (r *TriciumServer) Progress(c context.Context, req *tricium.ProgressRequest) (*tricium.ProgressResponse, error) {
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	runID, err := strconv.ParseInt(req.RunId, 10, 64)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to parse run ID: %s", req.RunId)
		return nil, grpc.Errorf(codes.InvalidArgument, "invalid run ID")
	}
	runState, analyzerProgress, err := progress(c, runID)
	if err != nil {
		logging.WithError(err).Errorf(c, "progress failed: %v, run ID: %d", err, runID)
		return nil, grpc.Errorf(codes.Internal, "failed to execute progress request")
	}
	logging.Infof(c, "[frontend] Analyzer progress: %v", analyzerProgress)
	return &tricium.ProgressResponse{
		State:            runState,
		AnalyzerProgress: analyzerProgress,
	}, nil
}

func progress(c context.Context, runID int64) (tricium.State, []*tricium.AnalyzerProgress, error) {
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", runID, nil)
	requestRes := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
	if err := ds.Get(c, requestRes); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to get AnalyzeRequestResult: %v", err)
	}
	run := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, run); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to get AnalyzeRequestResult: %v", err)
	}
	runKey := ds.KeyForObj(c, run)
	// TODO(emso): extract a common GetAnalyzerRunsForWorkflowRun function
	var analyzers []*track.AnalyzerRun
	for _, analyzerName := range run.Analyzers {
		analyzers = append(analyzers, &track.AnalyzerRun{ID: analyzerName, Parent: runKey})
	}
	if err := ds.Get(c, analyzers); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to get AnalyzerRun entities: %v", err)
	}
	var workerResults []*track.WorkerRunResult
	for _, analyzer := range analyzers {
		analyzerKey := ds.KeyForObj(c, analyzer)
		for _, workerName := range analyzer.Workers {
			workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, analyzerKey)
			workerResults = append(workerResults, &track.WorkerRunResult{ID: 1, Parent: workerKey})
		}
	}
	if err := ds.Get(c, workerResults); err != nil && err != ds.ErrNoSuchEntity {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to get WorkerRunResult entities: %v", err)
	}
	res := []*tricium.AnalyzerProgress{}
	for _, wr := range workerResults {
		res = append(res, &tricium.AnalyzerProgress{
			Analyzer:       wr.Analyzer,
			Platform:       wr.Platform,
			State:          wr.State,
			SwarmingTaskId: fmt.Sprintf("%s/task?id=%s", run.SwarmingServerURL, wr.SwarmingTaskID),
			NumComments:    int32(wr.NumComments),
		})
	}
	return requestRes.State, res, nil
}
