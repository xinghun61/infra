// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"encoding/json"
	"fmt"
	"strings"

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
	if req.IsolateServerUrl == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolate server URL")
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
	logging.Infof(c, "[tracker] Worker done (run ID: %d, worker: %s)", req.RunId, req.Worker)
	runKey, analyzerKey, workerKey := createKeys(c, req.RunId, req.Worker)
	worker := &track.WorkerInvocation{
		ID:     workerKey.StringID(),
		Parent: workerKey.Parent(),
	}
	// Collect and process isolated output.
	resultsStr, err := isolator.FetchIsolatedResults(c, req.IsolateServerUrl, req.IsolatedOutputHash)
	if err != nil {
		return fmt.Errorf("failed to fetch isolated worker resul: %v", err)
	}
	logging.Infof(c, "Fetched isolated result: %q", resultsStr)
	results := tricium.Data_Results{}
	if err := json.Unmarshal([]byte(resultsStr), &results); err != nil {
		return fmt.Errorf("failed to unmarshal results data: %v", err)
	}
	comments := []*track.ResultComment{}
	for _, comment := range results.Comments {
		json, err := json.Marshal(comment)
		if err != nil {
			return fmt.Errorf("failed to marshal comment data: %v", err)
		}
		key := ds.NewKey(c, "ResultComment", req.Worker, 0, workerKey)
		comments = append(comments, &track.ResultComment{
			ID:        key.StringID(),
			Parent:    key.Parent(),
			Comment:   string(json),
			Category:  comment.Category,
			Platforms: results.Platforms,
			Included:  true, // excluded later if needed
		})
	}
	// Update worker state.
	workerState := tricium.State_SUCCESS
	if req.ExitCode != 0 {
		workerState = tricium.State_FAILURE
	}
	// Prepare to update state of analyzer invocation.
	analyzer := &track.AnalyzerInvocation{
		ID:     analyzerKey.StringID(),
		Parent: analyzerKey.Parent(),
	}
	var workers []*track.WorkerInvocation
	if err := ds.GetAll(c, ds.NewQuery("WorkerInvocation").Ancestor(analyzerKey), &workers); err != nil {
		return fmt.Errorf("failed to retrieve worker invocations: %v", err)
	}
	analyzerState := tricium.State_SUCCESS
	for _, w := range workers {
		if w.Name == req.Worker {
			w.State = workerState // Setting state to what we will store in the below transaction.
		}
		// When all workers are done, aggregate the result.
		// All worker SUCCESSS -> analyzer SUCCESS
		// One or more workers FAILURE -> analyzer FAILURE
		if tricium.IsDone(w.State) {
			if w.State == tricium.State_FAILURE {
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
	// Prepare to update run state.
	run := &track.Run{ID: runKey.IntID()}
	var analyzers []*track.AnalyzerInvocation
	if err := ds.GetAll(c, ds.NewQuery("AnalyzerInvocation").Ancestor(runKey), &analyzers); err != nil {
		return fmt.Errorf("failed to retrieve analyzer invocations: %v", err)
	}
	analyzerName := strings.Split(req.Worker, "_")[0]
	runState := tricium.State_SUCCESS
	for _, a := range analyzers {
		if a.Name == analyzerName {
			a.State = analyzerState // Setting state to what will be stored in the below transaction.
		}
		// When all analyzers are done, aggregate the result.
		// All analyzers SUCCESSS -> run SUCCESS
		// One or more analyzers FAILURE -> run FAILURE
		if tricium.IsDone(a.State) {
			if a.State == tricium.State_FAILURE {
				runState = tricium.State_FAILURE
			}
		} else {
			// Found non-done analyzer, nothing to update - abort.
			runState = tricium.State_RUNNING // reset to launched.
			break
		}
	}
	return ds.RunInTransaction(c, func(c context.Context) (err error) {
		ops := []func() error{
			// Notify reporter.
			func() error {
				switch run.Reporter {
				case tricium.Reporter_GERRIT:
					// TOOD(emso): push notification to the Gerrit reporter
				default:
					// Do nothing.
				}
				return nil
			},
			// Add result comments.
			func() error {
				if err := ds.Put(c, comments); err != nil {
					return fmt.Errorf("failed to add result comments: %v", err)
				}
				return nil
			},
			// Update worker state, isolated output, and number of result comments.
			func() error {
				if err := ds.Get(c, worker); err != nil {
					return fmt.Errorf("failed to retrieve worker: %v", err)
				}
				if worker.State != workerState {
					worker.State = workerState
				}
				worker.IsolateServerURL = req.IsolateServerUrl
				worker.IsolatedOutput = req.IsolatedOutputHash
				worker.NumResultComments = len(results.Comments)
				if err := ds.Put(c, worker); err != nil {
					return fmt.Errorf("failed to mark worker as done-*: %v", err)
				}
				return nil
			},
			// Update analyzer state.
			func() error {
				if err := ds.Get(c, analyzer); err != nil {
					return fmt.Errorf("failed to retrieve analyzer: %v", err)
				}
				if analyzer.State != analyzerState {
					analyzer.State = analyzerState
					if err := ds.Put(c, analyzer); err != nil {
						return fmt.Errorf("failed to mark analyzer as done-*: %v", err)
					}
				}
				return nil
			},
			// Update run state. Stay in the main thread for this fourth operation.
			func() error {
				if err := ds.Get(c, run); err != nil {
					return fmt.Errorf("failed to retrieve run: %v", err)
				}
				if run.State != runState {
					run.State = runState
					if err := ds.Put(c, run); err != nil {
						return fmt.Errorf("failed to mark run as done-*: %v", err)
					}
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
	}, nil)
}

func createKeys(c context.Context, runID int64, worker string) (*ds.Key, *ds.Key, *ds.Key) {
	runKey := ds.NewKey(c, "Run", "", runID, nil)
	// Assuming that the analyzer name is included in the worker name, before the first underscore.
	analyzerName := strings.Split(worker, "_")[0]
	analyzerKey := ds.NewKey(c, "AnalyzerInvocation", analyzerName, 0, runKey)
	return runKey, analyzerKey, ds.NewKey(c, "WorkerInvocation", worker, 0, analyzerKey)
}
