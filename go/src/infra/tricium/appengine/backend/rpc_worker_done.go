// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"encoding/json"
	"strconv"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"github.com/google/uuid"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"

	"infra/qscheduler/qslib/tutils"
	admin "infra/tricium/api/admin/v1"
	apibq "infra/tricium/api/bigquery"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/gerrit"
	"infra/tricium/appengine/common/track"
)

// WorkerDone tracks the completion of a worker.
func (*trackerServer) WorkerDone(c context.Context, req *admin.WorkerDoneRequest) (res *admin.WorkerDoneResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	if err = validateWorkerDoneRequest(req); err != nil {
		return nil, errors.Annotate(err, "invalid request").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	if err = workerDone(c, req, common.IsolateServer); err != nil {
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
	if req.IsolatedOutputHash != "" && req.BuildbucketOutput != "" {
		return errors.New("too many results (both isolate and buildbucket exist)")
	}
	return nil
}

func workerDone(c context.Context, req *admin.WorkerDoneRequest, isolator common.IsolateAPI) error {
	logging.Fields{
		"runID":             req.RunId,
		"worker":            req.Worker,
		"isolatedNamespace": req.IsolatedNamespace,
		"isolatedOutput":    req.IsolatedOutputHash,
		"buildbucketOutput": req.BuildbucketOutput,
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
	if err = ds.Get(c, workerRes); err != nil {
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
	if err = ds.Get(c, run); err != nil {
		return errors.Annotate(err, "failed to get WorkflowRun").Err()
	}

	// Process output and collect comments.
	// This should only be done for successful analyzers with results.
	var comments []*track.Comment
	hasOutput := req.IsolatedOutputHash != "" || req.BuildbucketOutput != ""
	isAnalyzer := req.Provides == tricium.Data_RESULTS
	if req.State == tricium.State_SUCCESS && isAnalyzer && hasOutput {
		comments, err = collectComments(c, isolator, run.IsolateServerURL, req.IsolatedNamespace,
			req.IsolatedOutputHash, req.BuildbucketOutput, functionName, workerKey)
		if err != nil {
			return errors.Annotate(err, "failed to get worker results").Err()
		}
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
		p := ds.NewKey(c, "FunctionRun", name, 0, workflowRunKey)
		runResults = append(runResults, &track.FunctionRunResult{ID: 1, Parent: p})
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
		"worker":        req.Worker,
		"workerState":   req.State,
		"function":      functionName,
		"functionState": functionState,
		"runID":         req.RunId,
		"runState":      runState,
	}.Infof(c, "Updating state.")

	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return errors.Reason("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err).Err()
	}
	var selections []*track.CommentSelection
	numSelectedComments := 0

	// Now that all prerequisite data was loaded, run the mutations in a transaction.
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		return parallel.FanOutIn(func(taskC chan<- func() error) {
			// Add comments.
			taskC <- func() error {
				// Stop if there are no comments.
				if len(comments) == 0 {
					return nil
				}
				if err = ds.Put(c, comments); err != nil {
					return errors.Annotate(err, "failed to add Comment entries").Err()
				}
				entities := make([]interface{}, 0, len(comments)*2)
				selections, err = createCommentSelections(c, request, comments)
				if err != nil {
					logging.Warningf(c, "Error creating comment selections: %v", err)
					// On error still write the comment selections which specify they
					// were not included.
				}
				for i, comment := range comments {
					commentKey := ds.KeyForObj(c, comment)
					entities = append(entities, []interface{}{
						selections[i],
						&track.CommentFeedback{ID: 1, Parent: commentKey},
					}...)
					if selections[i].Included {
						numSelectedComments++
					}
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
						"function":    fr.Name,
						"numComments": fr.NumComments,
					}.Debugf(c, "Updating state of FunctionRunResult.")
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

	if !tricium.IsDone(functionState) {
		// Only report results to Gerrit and copy to BigQuery when done.
		return nil
	}

	// Notify reporter.
	if numSelectedComments > 0 && gerrit.IsGerritProjectRequest(request) {
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

	result := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
	if err := ds.Get(c, result); err != nil {
		return errors.Annotate(err, "failed to get AnalyzeRequestResult entity").Err()
	}
	return streamAnalysisResultsToBigQuery(c, workerRes, request, result, comments, selections)
}

// streamCommentsToBigQuery sends analyzer results to BigQuery for metrics and
// ad hoc analysis.
func streamAnalysisResultsToBigQuery(c context.Context, wres *track.WorkerRunResult, areq *track.AnalyzeRequest, ares *track.AnalyzeRequestResult, comments []*track.Comment, selections []*track.CommentSelection) error {
	run, err := createAnalysisResults(wres, areq, ares, comments, selections)
	if err != nil {
		return err
	}

	return common.ResultsLog.Insert(c, &bq.Row{Message: run})
}

// Create and populate an AnalysisRun given the datastore entities.
func createAnalysisResults(wres *track.WorkerRunResult, areq *track.AnalyzeRequest, ares *track.AnalyzeRequestResult, comments []*track.Comment, selections []*track.CommentSelection) (*apibq.AnalysisRun, error) {
	revisionNumber, err := strconv.Atoi(gerrit.PatchSetNumber(areq.GitRef))
	if err != nil {
		return nil, err
	}

	rev := tricium.GerritRevision{
		Host:    areq.GerritHost,
		Project: areq.Project,
		Change:  areq.GerritChange,
		GitUrl:  areq.GitURL,
		GitRef:  areq.GitRef,
	}

	files := make([]*tricium.Data_File, len(areq.Files))
	for i, f := range areq.Files {
		fc := tricium.Data_File(f)
		files[i] = &fc
	}

	gcomments := make([]*apibq.AnalysisRun_GerritComment, len(comments))
	for i, comment := range comments {
		ctime, err := ptypes.TimestampProto(comment.CreationTime)
		if err != nil {
			return nil, err
		}
		tcomment := tricium.Data_Comment{}
		if err = jsonpb.UnmarshalString(string(comment.Comment), &tcomment); err != nil {
			return nil, err
		}
		p, err := tricium.GetPlatforms(comment.Platforms)
		if err != nil {
			return nil, err
		}
		cinfo := apibq.AnalysisRun_GerritComment{
			Comment:     &tcomment,
			CreatedTime: ctime,
			Analyzer:    comment.Analyzer,
			Platforms:   p,
		}
		if selections != nil {
			cinfo.Selected = selections[i].Included
		}
		gcomments[i] = &cinfo
	}

	analysisRun := apibq.AnalysisRun{
		GerritRevision: &rev,
		RevisionNumber: int32(revisionNumber),
		Files:          files,
		RequestedTime:  tutils.TimestampProto(areq.Received),
		ResultState:    ares.State,
		ResultPlatform: wres.Platform,
		Comments:       gcomments,
	}

	return &analysisRun, nil
}

// createCommentSelections creates and puts track.CommentSelection entities.
//
// The CommentSelection determines whether the parent Comment is "included"
// (will be posted to Gerrit). The comment will be included if it is within
// the changed lines.
//
// In the future when there are multi-platform results, this could also
// decide which platform's results will be included. See: crbug.com/869177.
//
// The returned slice of track.CommentSelection will have the same size and
// order as |comments|.
func createCommentSelections(c context.Context, request *track.AnalyzeRequest, comments []*track.Comment) ([]*track.CommentSelection, error) {
	selections := make([]*track.CommentSelection, len(comments))
	for i, comment := range comments {
		commentKey := ds.KeyForObj(c, comment)
		selections[i] = &track.CommentSelection{
			ID:       1,
			Parent:   commentKey,
			Included: true, // Default value, may be overridden below.
		}
	}

	if !gerrit.IsGerritProjectRequest(request) {
		return selections, nil
	}

	// Get the changed lines for this revision.
	changedLines, err := gerrit.FetchChangedLines(c, request.GerritHost, request.GerritChange, request.GitRef)
	if err != nil {
		// Upon error, mark all of the comments as not selected.
		for _, s := range selections {
			s.Included = false
		}
		return selections, errors.Annotate(err, "failed to get changed lines").Err()
	}

	gerrit.FilterRequestChangedLines(request, &changedLines)

	for path, lines := range changedLines {
		logging.Debugf(c, "Num changed lines for %s is %d.", path, len(lines))
	}

	for i, comment := range comments {
		selections[i].Included = gerrit.CommentIsInChangedLines(c, comment, changedLines)
	}

	return selections, nil
}

// collectComments collects the comments in the results from the analyzer.
//
// Either isolatedNamespace and isolatedOutputHash, or buildbucketOutput, should be populated.
func collectComments(c context.Context, isolator common.IsolateAPI, isolateServerURL, isolatedNamespace, isolatedOutputHash, buildbucketOutput, analyzerName string, workerKey *ds.Key) ([]*track.Comment, error) {
	var comments []*track.Comment
	results := tricium.Data_Results{}
	// If isolate is present, fetch the data. Otherwise, unmarshal the buildbucket output.
	if isolatedOutputHash != "" {
		resultsStr, err := isolator.FetchIsolatedResults(c, isolateServerURL, isolatedNamespace, isolatedOutputHash)
		if err != nil {
			return comments, errors.Annotate(err, "failed to fetch isolated worker result").Err()
		}
		logging.Infof(c, "Fetched isolated result (%q, %q): %q", isolatedNamespace, isolatedOutputHash, resultsStr)
		if err := jsonpb.UnmarshalString(resultsStr, &results); err != nil {
			return comments, errors.Annotate(err, "failed to unmarshal results data").Err()
		}
	} else {
		if err := json.Unmarshal([]byte(buildbucketOutput), &results); err != nil {
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
