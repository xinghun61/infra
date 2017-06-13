// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"encoding/json"
	"fmt"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

// WorkerDone tracks the completion of a worker.
func (*trackerServer) WorkerDone(c context.Context, req *admin.WorkerDoneRequest) (*admin.WorkerDoneResponse, error) {
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if req.Worker == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing worker")
	}
	if req.IsolatedOutputHash == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing output hash")
	}
	// TODO(emso): check exit code
	if err := workerDone(c, req, common.IsolateServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track worker completion: %v", err)
	}
	return &admin.WorkerDoneResponse{}, nil
}

func workerDone(c context.Context, req *admin.WorkerDoneRequest, isolator common.IsolateAPI) error {
	logging.Debugf(c, "[tracker] Worker done (run ID: %d, worker: %s)", req.RunId, req.Worker)
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	analyzerName, err := track.ExtractAnalyzerName(req.Worker)
	if err != nil {
		return fmt.Errorf("failed to extract analyzer name: %v", err)
	}
	analyzerKey := ds.NewKey(c, "AnalyzerRun", analyzerName, 0, runKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, analyzerKey)
	// Collect and process isolated output.
	run := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, run); err != nil {
		return fmt.Errorf("failed to get WorkflowRun: %v", err)
	}
	resultsStr, err := isolator.FetchIsolatedResults(c, run.IsolateServerURL, req.IsolatedOutputHash)
	if err != nil {
		return fmt.Errorf("failed to fetch isolated worker result: %v", err)
	}
	logging.Infof(c, "Fetched isolated result: %q", resultsStr)
	results := tricium.Data_Results{}
	if err := json.Unmarshal([]byte(resultsStr), &results); err != nil {
		return fmt.Errorf("failed to unmarshal results data: %v", err)
	}
	comments := []*track.Comment{}
	for _, comment := range results.Comments {
		json, err := json.Marshal(comment)
		if err != nil {
			return fmt.Errorf("failed to marshal comment data: %v", err)
		}
		comments = append(comments, &track.Comment{
			Parent:    workerKey,
			Comment:   json,
			Category:  comment.Category,
			Platforms: results.Platforms,
		})
	}
	// Compute state of this worker that is done.
	workerState := tricium.State_SUCCESS
	if req.ExitCode != 0 {
		workerState = tricium.State_FAILURE
	}
	// Compute state of parent analyzer.
	analyzer := &track.AnalyzerRun{ID: analyzerName, Parent: runKey}
	if err := ds.Get(c, analyzer); err != nil {
		return fmt.Errorf("failed to get AnalyzerRun entity: %v", err)
	}
	workerResults := []*track.WorkerRunResult{}
	for _, workerName := range analyzer.Workers {
		workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, analyzerKey)
		workerResults = append(workerResults, &track.WorkerRunResult{ID: 1, Parent: workerKey})
	}
	if err := ds.Get(c, workerResults); err != nil {
		return fmt.Errorf("failed to get WorkerRunResult entities: %v", err)
	}
	analyzerState := tricium.State_SUCCESS
	for _, wr := range workerResults {
		if wr.Name == req.Worker {
			wr.State = workerState // Setting state to what we will store in the below transaction.
		}
		// When all workers are done, aggregate the result.
		// All worker SUCCESSS -> analyzer SUCCESS
		// One or more workers FAILURE -> analyzer FAILURE
		if tricium.IsDone(wr.State) {
			if wr.State == tricium.State_FAILURE {
				analyzerState = tricium.State_FAILURE
			}
		} else {
			// Found non-done worker, no change to be made - abort.
			analyzerState = tricium.State_RUNNING // reset to launched.
			break
		}
	}
	// If analyzer is done then we should merge results if needed.
	if tricium.IsDone(analyzerState) {
		// TODO(emso): merge results.
		// Review comments in this invocation and stored comments from sibling workers.
		// Comments are included by default. For conflicting comments, select which comments
		// to include and set other comments include to false.
	}
	// Compute run state.
	var analyzerResults []*track.AnalyzerRunResult
	for _, analyzerName := range run.Analyzers {
		analyzerKey := ds.NewKey(c, "AnalyzerRun", analyzerName, 0, runKey)
		analyzerResults = append(analyzerResults, &track.AnalyzerRunResult{ID: 1, Parent: analyzerKey})
	}
	if err := ds.Get(c, analyzerResults); err != nil {
		return fmt.Errorf("failed to retrieve AnalyzerRunResult entities: %v", err)
	}
	runState := tricium.State_SUCCESS
	for _, ar := range analyzerResults {
		if ar.Name == analyzerName {
			ar.State = analyzerState // Setting state to what will be stored in the below transaction.
		}
		// When all analyzers are done, aggregate the result.
		// All analyzers SUCCESSS -> run SUCCESS
		// One or more analyzers FAILURE -> run FAILURE
		if tricium.IsDone(ar.State) {
			if ar.State == tricium.State_FAILURE {
				runState = tricium.State_FAILURE
			}
		} else {
			// Found non-done analyzer, nothing to update - abort.
			runState = tricium.State_RUNNING // reset to launched.
			break
		}
	}
	ops := []func() error{
		// Add comments.
		func() error {
			if err := ds.Put(c, comments); err != nil {
				return fmt.Errorf("failed to add Comment entries: %v", err)
			}
			entities := make([]interface{}, 0, len(comments)*2)
			for _, comment := range comments {
				commentKey := ds.KeyForObj(c, comment)
				entities = append(entities, []interface{}{
					&track.CommentSelection{
						ID:       1,
						Parent:   commentKey,
						Included: true, // TODO(emso): merging
					},
					&track.CommentFeedback{ID: 1, Parent: commentKey},
				}...)
			}
			if err := ds.Put(c, entities); err != nil {
				return fmt.Errorf("failed to add CommentSelection/CommentFeedback entries: %v", err)
			}
			return nil
		},
		// Update worker state, isolated output, and number of result comments.
		func() error {
			wr := &track.WorkerRunResult{
				ID:             1,
				Parent:         workerKey,
				State:          workerState,
				IsolatedOutput: req.IsolatedOutputHash,
				NumComments:    len(results.Comments),
			}
			if err := ds.Put(c, wr); err != nil {
				return fmt.Errorf("failed to update WorkerRunResult: %v", err)
			}
			return nil
		},
		// Update analyzer state.
		func() error {
			ar := &track.AnalyzerRunResult{ID: 1, Parent: analyzerKey}
			if err := ds.Get(c, ar); err != nil {
				return fmt.Errorf("failed to get AnalyzerRunResult (analyzer:%s): %v", analyzerName, err)
			}
			if ar.State != analyzerState {
				ar.State = analyzerState
				if err := ds.Put(c, ar); err != nil {
					return fmt.Errorf("failed to update AnalyzerRunResult: %v", err)
				}
			}
			return nil
		},
		// Update run state.
		func() error {
			rr := &track.WorkflowRunResult{ID: 1, Parent: runKey}
			if err := ds.Get(c, rr); err != nil {
				return fmt.Errorf("failed to get WorkflowRunResult entry: %v", err)
			}
			if rr.State != runState {
				rr.State = runState
				if err := ds.Put(c, rr); err != nil {
					return fmt.Errorf("failed to update WorkflowRunResult entry: %v", err)
				}
			}
			return nil
		},
	}
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		return common.RunInParallel(ops)
	}, nil); err != nil {
		return err
	}
	// Notify reporter.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return fmt.Errorf("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err)
	}
	switch request.Reporter {
	case tricium.Reporter_GERRIT:
		// TOOD(emso): push notification to the Gerrit reporter
	default:
		// Do nothing.
	}
	return nil
}
