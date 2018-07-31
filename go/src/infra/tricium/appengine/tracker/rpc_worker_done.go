// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"encoding/json"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/google/uuid"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

// WorkerDone tracks the completion of a worker.
func (*trackerServer) WorkerDone(c context.Context, req *admin.WorkerDoneRequest) (res *admin.WorkerDoneResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	if err := validateWorkerDoneRequest(req); err != nil {
		return nil, errors.Annotate(err, "invalid request").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	if err := workerDone(c, req, common.IsolateServer); err != nil {
		return nil, errors.Annotate(err, "failed to track worker completion").Tag(grpcutil.InternalTag).Err()
	}
	return &admin.WorkerDoneResponse{}, nil
}

// validateWorkerDoneRequest returns an error if the request is invalid.
//
// The returned error should be tagged for gRPC by the caller.
func validateWorkerDoneRequest(req *admin.WorkerDoneRequest) error {
	if req.RunId == 0 {
		return errors.New("missing run ID")
	}
	if req.Worker == "" {
		return errors.New("missing worker")
	}
	if req.IsolatedOutputHash == "" && req.BuildbucketOutput == "" {
		return errors.New("missing output")
	}
	if req.IsolatedOutputHash != "" && req.BuildbucketOutput != "" {
		return errors.New("too many results (both isolate and buildbucket exist)")
	}
	return nil
}

func workerDone(c context.Context, req *admin.WorkerDoneRequest, isolator common.IsolateAPI) error {
	logging.Fields{
		"run ID":             req.RunId,
		"worker":             req.Worker,
		"isolated output":    req.IsolatedOutputHash,
		"buildbucket output": req.BuildbucketOutput,
	}.Infof(c, "[tracker] Worker done request received.")

	// Get keys for entities.
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	workflowRunKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	functionName, platformName, err := track.ExtractFunctionPlatform(req.Worker)
	if err != nil {
		return errors.Annotate(err, "failed to extract function name").Err()
	}
	functionRunKey := ds.NewKey(c, "FunctionRun", functionName, 0, workflowRunKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, functionRunKey)

	// If this worker is already marked as done, abort.
	workerRes := &track.WorkerRunResult{ID: 1, Parent: workerKey}
	if err := ds.Get(c, workerRes); err != nil {
		return errors.Annotate(err, "failed to read state of WorkerRunResult").Err()
	}
	if tricium.IsDone(workerRes.State) {
		logging.Fields{
			"worker": workerRes.Name,
		}.Infof(c, "Worker already tracked as done.")
		return nil
	}

	// Get run entity for this worker.
	run := &track.WorkflowRun{ID: 1, Parent: requestKey}
	if err := ds.Get(c, run); err != nil {
		return errors.Annotate(err, "failed to get WorkflowRun").Err()
	}

	// Process isolated/buildbucket output and collect comments.
	// NB! This only applies to successful analyzer functions outputting comments.
	comments, err := collectComments(c, req.State, req.Provides, isolator, run.IsolateServerURL,
		req.IsolatedOutputHash, req.BuildbucketOutput, functionName, workerKey)
	if err != nil {
		return errors.Annotate(err, "failed to get worker results").Err()
	}

	// Compute state of parent function.
	functionRun := &track.FunctionRun{ID: functionName, Parent: workflowRunKey}
	if err := ds.Get(c, functionRun); err != nil {
		return errors.Annotate(err, "failed to get FunctionRun entity").Err()
	}
	workerResults := []*track.WorkerRunResult{}
	for _, workerName := range functionRun.Workers {
		workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, functionRunKey)
		workerResults = append(workerResults, &track.WorkerRunResult{ID: 1, Parent: workerKey})
	}
	if err := ds.Get(c, workerResults); err != nil {
		return errors.Annotate(err, "failed to get WorkerRunResult entities").Err()
	}
	functionState := tricium.State_SUCCESS
	functionNumComments := len(comments)
	for _, wr := range workerResults {
		if wr.Name == req.Worker {
			wr.State = req.State // Setting state to what we will store in the below transaction.
		} else {
			functionNumComments += wr.NumComments
		}
		// When all workers are done, aggregate the result; The
		// function is considered successful when all workers are
		// successful.
		if tricium.IsDone(wr.State) {
			if wr.State != tricium.State_SUCCESS {
				functionState = tricium.State_FAILURE
			}
		} else {
			// Found non-done worker, no change to be made.
			// Abort and reset state to running (launched).
			functionState = tricium.State_RUNNING
			break
		}
	}

	// If the function is done, then we should merge results if needed.
	if tricium.IsDone(functionState) {
		logging.Fields{
			"analyzer":     functionName,
			"num comments": functionNumComments,
		}.Infof(c, "Analyzer completed.")
		// TODO(crbug.com/869177): Merge results.
		// Review comments in this invocation and stored comments from sibling
		// workers. Comments are included by default. For conflicting comments,
		// select which comments to include.
	}

	// Compute the overall worflow run state.
	var runResults []*track.FunctionRunResult
	for _, name := range run.Functions {
		functionRunKey := ds.NewKey(c, "FunctionRun", name, 0, workflowRunKey)
		runResults = append(runResults, &track.FunctionRunResult{ID: 1, Parent: functionRunKey})
	}
	if err := ds.Get(c, runResults); err != nil {
		return errors.Annotate(err, "failed to retrieve FunctionRunResult entities").Err()
	}
	runState := tricium.State_SUCCESS
	runNumComments := functionNumComments
	for _, fr := range runResults {
		if fr.Name == functionName {
			fr.State = functionState // Setting state to what will be stored in the below transaction.
		} else {
			runNumComments += fr.NumComments
		}
		// When all functions are done, aggregate the result.
		// All functions SUCCESS -> run SUCCESS
		// Otherwise -> run FAILURE
		if tricium.IsDone(fr.State) {
			if fr.State != tricium.State_SUCCESS {
				runState = tricium.State_FAILURE
			}
		} else {
			// Found non-done function, nothing to update - abort.
			runState = tricium.State_RUNNING // reset to launched.
			break
		}
	}

	logging.Fields{
		"worker":         req.Worker,
		"worker state":   req.State,
		"function":       functionName,
		"function state": functionState,
		"run ID":         req.RunId,
		"run state":      runState,
	}.Infof(c, "Updating state.")

	// Now that all prerequisite data was loaded, run the mutations in a transaction.
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		return parallel.FanOutIn(func(taskC chan<- func() error) {
			// Add comments.
			taskC <- func() error {
				// Stop if there are no comments.
				if len(comments) == 0 {
					return nil
				}
				if err := ds.Put(c, comments); err != nil {
					return errors.Annotate(err, "failed to add Comment entries").Err()
				}
				entities := make([]interface{}, 0, len(comments)*2)
				for _, comment := range comments {
					commentKey := ds.KeyForObj(c, comment)
					entities = append(entities, []interface{}{
						&track.CommentSelection{
							ID:       1,
							Parent:   commentKey,
							Included: true, // TODO(crbug.com/869177): Merge results.
						},
						&track.CommentFeedback{ID: 1, Parent: commentKey},
					}...)
				}
				if err := ds.Put(c, entities); err != nil {
					return errors.Annotate(err, "failed to add CommentSelection/CommentFeedback entries").Err()
				}
				// Monitor comment count per category.
				commentCount.Set(c, int64(len(comments)), functionName, platformName)
				return nil
			}

			// Update worker state, isolated output, and number of result comments.
			taskC <- func() error {
				workerRes.State = req.State
				workerRes.IsolatedOutput = req.IsolatedOutputHash
				workerRes.BuildbucketOutput = req.BuildbucketOutput
				workerRes.NumComments = len(comments)
				if err := ds.Put(c, workerRes); err != nil {
					return errors.Annotate(err, "failed to update WorkerRunResult").Err()
				}
				// Monitor worker success/failure.
				if req.State == tricium.State_SUCCESS {
					workerSuccessCount.Add(c, 1, functionName, platformName)
				} else {
					workerFailureCount.Add(c, 1, functionName, platformName, req.State.String())
				}
				return nil
			}

			// Update function state.
			taskC <- func() error {
				fr := &track.FunctionRunResult{ID: 1, Parent: functionRunKey}
				if err := ds.Get(c, fr); err != nil {
					return errors.Annotate(err, "failed to get FunctionRunResult (function: %s)", functionName).Err()
				}
				if fr.State != functionState {
					fr.State = functionState
					fr.NumComments = functionNumComments
					logging.Fields{
						"function":     fr.Name,
						"num comments": fr.NumComments,
					}.Debugf(c, "[tracker] Updating state of function.")
					if err := ds.Put(c, fr); err != nil {
						return errors.Annotate(err, "failed to update FunctionRunResult").Err()
					}
				}
				return nil
			}

			// Update run state.
			taskC <- func() error {
				rr := &track.WorkflowRunResult{ID: 1, Parent: workflowRunKey}
				if err := ds.Get(c, rr); err != nil {
					return errors.Annotate(err, "failed to get WorkflowRunResult entity").Err()
				}
				if rr.State != runState {
					rr.State = runState
					rr.NumComments = runNumComments
					if err := ds.Put(c, rr); err != nil {
						return errors.Annotate(err, "failed to update WorkflowRunResult entity").Err()
					}
				}
				return nil
			}

			// Update request state.
			taskC <- func() error {
				if !tricium.IsDone(runState) {
					return nil
				}
				ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
				if err := ds.Get(c, ar); err != nil {
					return errors.Annotate(err, "failed to get AnalyzeRequestResult entity").Err()
				}
				if ar.State != runState {
					ar.State = runState
					if err := ds.Put(c, ar); err != nil {
						return errors.Annotate(err, "failed to update AnalyzeRequestResult entity").Err()
					}
				}
				return nil
			}
		})
	}, nil); err != nil {
		return err
	}

	// Notify reporter.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return errors.Reason("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err).Err()
	}
	if request.GerritProject != "" && request.GerritChange != "" {
		if tricium.IsDone(functionState) {
			// Only report results if there were comments.
			if len(comments) == 0 {
				return nil
			}
			b, err := proto.Marshal(&admin.ReportResultsRequest{
				RunId:    req.RunId,
				Analyzer: functionRun.ID,
			})
			if err != nil {
				return errors.Annotate(err, "failed to encode ReportResults request").Err()
			}
			t := tq.NewPOSTTask("/gerrit/internal/report-results", nil)
			t.Payload = b
			if err = tq.Add(c, common.GerritReporterQueue, t); err != nil {
				return errors.Annotate(err, "failed to enqueue reporter results request").Err()
			}
		}
	}
	return nil
}

// collectComments collects the comments in the results from the analyzer.
//
// Exactly one of isolatedOutputHash and buildbucketOutput should be populated.
func collectComments(c context.Context, state tricium.State, t tricium.Data_Type, isolator common.IsolateAPI,
	isolateServerURL, isolatedOutputHash, buildbucketOutput, analyzerName string, workerKey *ds.Key) ([]*track.Comment, error) {
	var comments []*track.Comment

	// Only collect comments if function completed successfully.
	if state != tricium.State_SUCCESS {
		return comments, nil
	}
	// Only collect comments if the function is an analyzer.
	if t != tricium.Data_RESULTS {
		return comments, nil
	}

	results := tricium.Data_Results{}
	if buildbucketOutput != "" {
		if err := json.Unmarshal([]byte(buildbucketOutput), &results); err != nil {
			return comments, errors.Annotate(err, "failed to unmarshal results data").Err()
		}
	} else {
		resultsStr, err := isolator.FetchIsolatedResults(c, isolateServerURL, isolatedOutputHash)
		if err != nil {
			return comments, errors.Annotate(err, "failed to fetch isolated worker result").Err()
		}
		logging.Infof(c, "Fetched isolated result (%q): %q", isolatedOutputHash, resultsStr)
		if err := jsonpb.UnmarshalString(resultsStr, &results); err != nil {
			return comments, errors.Annotate(err, "failed to unmarshal results data").Err()
		}
	}
	for _, comment := range results.Comments {
		uuid, err := uuid.NewRandom()
		if err != nil {
			return comments, errors.Annotate(err, "failed to generated UUID for comment").Err()
		}
		comment.Id = uuid.String()
		j, err := (&jsonpb.Marshaler{}).MarshalToString(comment)
		if err != nil {
			return comments, errors.Annotate(err, "failed to marshal comment data").Err()
		}
		comments = append(comments, &track.Comment{
			Parent:       workerKey,
			UUID:         uuid.String(),
			CreationTime: clock.Now(c).UTC(),
			Comment:      []byte(j),
			Analyzer:     analyzerName,
			Category:     comment.Category,
			Platforms:    results.Platforms,
		})
	}
	return comments, nil
}
