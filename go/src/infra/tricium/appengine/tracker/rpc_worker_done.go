// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"encoding/json"
	"fmt"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"

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
	logging.Debugf(c, "[tracker] Worker done (run ID: %d, worker: %q, isolated output: %q)",
		req.RunId, req.Worker, req.IsolatedOutputHash)

	// Get keys for entities.
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	analyzerName, err := track.ExtractAnalyzerName(req.Worker)
	if err != nil {
		return fmt.Errorf("failed to extract analyzer name: %v", err)
	}
	analyzerKey := ds.NewKey(c, "AnalyzerRun", analyzerName, 0, runKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, analyzerKey)

	// If this worker is already marked as done, abort.
	workerRes := &track.WorkerRunResult{ID: 1, Parent: workerKey}
	if err := ds.Get(c, workerRes); err != nil {
		return fmt.Errorf("failed to read state of WorkerRunResult: %v", err)
	}
	if tricium.IsDone(workerRes.State) {
		logging.Infof(c, "Worker (%s) already tracked as done", workerRes.Name)
		return nil
	}

	// Get run entity for this worker.
	run := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, run); err != nil {
		return fmt.Errorf("failed to get WorkflowRun: %v", err)
	}

	// Process isolated output and collect comments.
	// NB! This only applies to analyzers outputting comments.
	comments, err := collectComments(c, req.Provides, isolator, run.IsolateServerURL, req.IsolatedOutputHash, workerKey)
	if err != nil {
		return fmt.Errorf("failed to get worker results: %v", err)
	}

	// Compute state of this worker.
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
	analyzerNumComments := len(comments)
	for _, wr := range workerResults {
		if wr.Name == req.Worker {
			wr.State = workerState // Setting state to what we will store in the below transaction.
		} else {
			analyzerNumComments += wr.NumComments
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
		logging.Infof(c, "Analyzer %s completed with %d comments", analyzerName, analyzerNumComments)
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
	runNumComments := analyzerNumComments
	for _, ar := range analyzerResults {
		if ar.Name == analyzerName {
			ar.State = analyzerState // Setting state to what will be stored in the below transaction.
		} else {
			runNumComments += ar.NumComments
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

	// Write state changes and results in parallel in a transaction.
	logging.Infof(c, "Updating state: worker %s: %s, analyzer %s: %s, run %s, %s",
		req.Worker, workerState, analyzerName, analyzerState, req.RunId, runState)

	// Now that all prerequisite data was loaded, run the mutations in a transaction.
	ops := []func() error{
		// Add comments.
		func() error {
			// Stop if there are no comments.
			if len(comments) == 0 {
				return nil
			}
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
			workerRes.State = workerState
			workerRes.IsolatedOutput = req.IsolatedOutputHash
			workerRes.NumComments = len(comments)
			if err := ds.Put(c, workerRes); err != nil {
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
				ar.NumComments = analyzerNumComments
				logging.Debugf(c, "[tracker] Updating state of analyzer %s, num comments: %d", ar.Name, ar.NumComments)
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
				return fmt.Errorf("failed to get WorkflowRunResult entity: %v", err)
			}
			if rr.State != runState {
				rr.State = runState
				rr.NumComments = runNumComments
				if err := ds.Put(c, rr); err != nil {
					return fmt.Errorf("failed to update WorkflowRunResult entity: %v", err)
				}
			}
			return nil
		},
		// Update request state.
		func() error {
			if !tricium.IsDone(runState) {
				return nil
			}
			ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			if err := ds.Get(c, ar); err != nil {
				return fmt.Errorf("failed to get AnalyzeRequestResult entity: %v", err)
			}
			if ar.State != runState {
				ar.State = runState
				if err := ds.Put(c, ar); err != nil {
					return fmt.Errorf("failed to update AnalyzeRequestResult entity: %v", err)
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
	switch request.Consumer {
	case tricium.Consumer_GERRIT:
		if tricium.IsDone(analyzerState) {
			// Only report results if there were comments.
			if len(comments) == 0 {
				return nil
			}
			b, err := proto.Marshal(&admin.ReportResultsRequest{
				RunId:    req.RunId,
				Analyzer: analyzer.ID,
			})
			if err != nil {
				return fmt.Errorf("failed to encode ReportResults request: %v", err)
			}
			t := tq.NewPOSTTask("/gerrit/internal/report-results", nil)
			t.Payload = b
			if err = tq.Add(c, common.GerritReporterQueue, t); err != nil {
				return fmt.Errorf("failed to enqueue reporter results request: %v", err)
			}
		}
		if tricium.IsDone(runState) {
			b, err := proto.Marshal(&admin.ReportCompletedRequest{RunId: req.RunId})
			if err != nil {
				return fmt.Errorf("failed to encode ReportCompleted request: %v", err)
			}
			t := tq.NewPOSTTask("/gerrit/internal/report-completed", nil)
			t.Payload = b
			if err = tq.Add(c, common.GerritReporterQueue, t); err != nil {
				return fmt.Errorf("failed to enqueue reporter complete request: %v", err)
			}
		}
	default:
		// Do nothing.
	}
	return nil
}

func collectComments(c context.Context, t tricium.Data_Type, isolator common.IsolateAPI,
	isolateServerURL, isolatedOutputHash string, workerKey *ds.Key) ([]*track.Comment, error) {
	comments := []*track.Comment{}
	switch t {
	case tricium.Data_RESULTS:
		resultsStr, err := isolator.FetchIsolatedResults(c, isolateServerURL, isolatedOutputHash)
		if err != nil {
			return comments, fmt.Errorf("failed to fetch isolated worker result: %v", err)
		}
		logging.Infof(c, "Fetched isolated result (%q): %q", isolatedOutputHash, resultsStr)
		results := tricium.Data_Results{}
		if err := json.Unmarshal([]byte(resultsStr), &results); err != nil {
			return comments, fmt.Errorf("failed to unmarshal results data: %v", err)
		}
		for _, comment := range results.Comments {
			j, err := json.Marshal(comment)
			if err != nil {
				return comments, fmt.Errorf("failed to marshal comment data: %v", err)
			}
			comments = append(comments, &track.Comment{
				Parent:    workerKey,
				Comment:   j,
				Category:  comment.Category,
				Platforms: results.Platforms,
			})
		}
	default:
		// No comments.
	}
	return comments, nil
}
