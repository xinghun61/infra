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
	"go.chromium.org/luci/common/data/stringset"
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
	workflowKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	functionName, platformName, err := track.ExtractFunctionPlatform(req.Worker)
	if err != nil {
		return errors.Annotate(err, "failed to extract function name").Err()
	}
	functionKey := ds.NewKey(c, "FunctionRun", functionName, 0, workflowKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, functionKey)

	// If this worker is already marked as done, abort.
	workerResult := &track.WorkerRunResult{ID: 1, Parent: workerKey}
	if err = ds.Get(c, workerResult); err != nil {
		return errors.Annotate(err, "failed to get WorkerRunResult").Err()
	}
	if tricium.IsDone(workerResult.State) {
		logging.Fields{
			"worker": workerResult.Name,
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
	functionRun := &track.FunctionRun{ID: functionName, Parent: workflowKey}
	if err := ds.Get(c, functionRun); err != nil {
		return errors.Annotate(err, "failed to get FunctionRun entity").Err()
	}
	workerResults := []*track.WorkerRunResult{}
	for _, workerName := range functionRun.Workers {
		workerKey := ds.NewKey(c, "WorkerRun", workerName, 0, functionKey)
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

	// Compute the overall worflow run state; this is based on the states of
	// functions in the workflow. If any workers are RUNNING, it is RUNNING. If
	// all are SUCCESS, it is SUCCESS; otherwise it is FAILURE.
	var functionResults []*track.FunctionRunResult
	for _, name := range run.Functions {
		p := ds.NewKey(c, "FunctionRun", name, 0, workflowKey)
		functionResults = append(functionResults, &track.FunctionRunResult{ID: 1, Parent: p})
	}
	if err := ds.Get(c, functionResults); err != nil {
		return errors.Annotate(err, "failed to retrieve FunctionRunResult entities").Err()
	}
	// runState and runNumComments are the overall aggregated state for the
	// workflow, which is stored in both WorkflowRunResult and
	// AnalyzeRequestResult.
	runState := tricium.State_SUCCESS
	runNumComments := functionNumComments
	for _, fr := range functionResults {
		if fr.Name == functionName {
			// Update entity; this will be written in the transaction below.
			fr.State = functionState
		} else {
			runNumComments += fr.NumComments
		}
		// When all functions are done, aggregate the result. All functions
		// SUCCESS -> workflow SUCCESS; otherwise workflow FAILURE.
		if tricium.IsDone(fr.State) {
			if fr.State != tricium.State_SUCCESS {
				runState = tricium.State_FAILURE
			}
		} else {
			// Found non-done function, so the workflow run is not yet done.
			runState = tricium.State_RUNNING
			break
		}
	}

	logging.Fields{
		"workerName":    req.Worker,
		"workerState":   req.State,
		"functionName":  functionName,
		"functionState": functionState,
		"runID":         req.RunId,
		"runState":      runState,
	}.Infof(c, "Updating state.")

	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return errors.Reason("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err).Err()
	}
	selections, err := createCommentSelections(c, request, comments)
	// Even on error, createCommentSelections is expected to always return a
	// slice of CommentSelection that may be used below.
	if len(selections) != len(comments) {
		return errors.Reason("unexpected number of CommentSelections (%d, expected %d)", len(selections), len(comments)).Err()
	}
	if err != nil {
		logging.Warningf(c, "Error creating CommentSelections: %v", err)
	}
	numSelectedComments := 0
	for _, s := range selections {
		if s.Included {
			numSelectedComments++
		}
	}

	// Now that all prerequisite data was loaded, run the mutations in a transaction.
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		// If there were comments produced, add all Comment, CommentFeedback,
		// and CommentSelection entities.
		if len(comments) > 0 {
			if err = ds.Put(c, comments); err != nil {
				return errors.Annotate(err, "failed to add Comment entities ").Err()
			}
			entities := make([]interface{}, 0, len(comments)*2)
			for i, comment := range comments {
				commentKey := ds.KeyForObj(c, comment)
				selections[i].Parent = commentKey
				entities = append(entities, selections[i])
				entities = append(entities, &track.CommentFeedback{ID: 1, Parent: commentKey})
			}
			if err := ds.Put(c, entities); err != nil {
				return errors.Annotate(err, "failed to add CommentFeedback or CommentSelection entries").Err()
			}
		}

		// Update WorkerRunResult state, isolated or buildbucket output, and
		// comment count.
		workerResult.State = req.State
		workerResult.IsolatedOutput = req.IsolatedOutputHash
		workerResult.BuildbucketOutput = req.BuildbucketOutput
		workerResult.NumComments = len(comments)
		if err := ds.Put(c, workerResult); err != nil {
			return errors.Annotate(err, "failed to update WorkerRunResult").Err()
		}

		// Update FunctionRunResult state and comment count.
		functionResult := &track.FunctionRunResult{ID: 1, Parent: functionKey}
		if err := ds.Get(c, functionResult); err != nil {
			return errors.Annotate(err, "failed to get FunctionRunResult (function: %s)", functionName).Err()
		}
		if functionResult.State != functionState {
			functionResult.State = functionState
			functionResult.NumComments = functionNumComments
			if err := ds.Put(c, functionResult); err != nil {
				return errors.Annotate(err, "failed to update FunctionRunResult").Err()
			}
		}

		// Update WorkflowRunResult state and comment count.
		workflowResult := &track.WorkflowRunResult{ID: 1, Parent: workflowKey}
		if err := ds.Get(c, workflowResult); err != nil {
			return errors.Annotate(err, "failed to get WorkflowRunResult entity").Err()
		}
		if workflowResult.State != runState {
			workflowResult.State = runState
			workflowResult.NumComments = runNumComments
			if err := ds.Put(c, workflowResult); err != nil {
				return errors.Annotate(err, "failed to update WorkflowRunResult entity").Err()
			}
		}

		// Update AnalyzeRequestResult state.
		if tricium.IsDone(runState) {
			requestResult := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			if err := ds.Get(c, requestResult); err != nil {
				return errors.Annotate(err, "failed to get AnalyzeRequestResult entity").Err()
			}
			if requestResult.State != runState {
				requestResult.State = runState
				if err := ds.Put(c, requestResult); err != nil {
					return errors.Annotate(err, "failed to update AnalyzeRequestResult entity").Err()
				}
			}
		}
		return nil
	}, nil); err != nil {
		return err
	}

	// Monitor comment count per category and worker success/failure. Metric
	// updates are done after the transaction to prevent double-counting in the
	// case of transaction retries.
	if len(comments) > 0 {
		commentCount.Add(c, int64(len(comments)), functionName, platformName)
	}
	if req.State == tricium.State_SUCCESS {
		workerSuccessCount.Add(c, 1, functionName, platformName)
	} else {
		workerFailureCount.Add(c, 1, functionName, platformName, req.State.String())
	}

	if !tricium.IsDone(functionState) {
		return nil
	}

	// If there are now comments ready to post, we want to enqueue a request to
	// report the results to Gerrit.
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
	return streamAnalysisResultsToBigQuery(c, workerResult, request, result, comments, selections)
}

// streamAnalysisResultsToBigQuery sends results to BigQuery.
func streamAnalysisResultsToBigQuery(c context.Context, wres *track.WorkerRunResult, areq *track.AnalyzeRequest, ares *track.AnalyzeRequestResult, comments []*track.Comment, selections []*track.CommentSelection) error {
	run, err := createAnalysisResults(wres, areq, ares, comments, selections)
	if err != nil {
		return err
	}

	return common.ResultsLog.Insert(c, &bq.Row{Message: run})
}

// createAnalysisResults creates and populate an AnalysisRun to send BQ.
//
// In general, there is one AnalysisRun created for each analyzer, although
// each AnalysisRun may contain data about the analyze request, e.g. overall
// request state, and original request time.
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
//
// The given comments may not have been put in datastore and thus may not yet
// have valid IDs, so the Parent key is not set in any of the returned
// CommentSelection entities.
func createCommentSelections(c context.Context, request *track.AnalyzeRequest, comments []*track.Comment) ([]*track.CommentSelection, error) {
	selections := make([]*track.CommentSelection, len(comments))
	for i := range comments {
		// Default to Included: true; this value may be overridden below.
		selections[i] = &track.CommentSelection{ID: 1, Included: true}
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

	// We want to suppress comments that are "similar" to those that have
	// been reported as not useful.
	//
	// One simple way to match "similar" comments is by the comment category
	// string. This could potentially be changed to match by comment text or
	// some combination of comment properties.
	categories := suppressedCategories(c, request.GerritHost, request.GerritChange)

	for i, comment := range comments {
		isChanged := gerrit.CommentIsInChangedLines(c, comment, changedLines)
		isSuppressed := categories.Has(comment.Category)
		tcomment := tricium.Data_Comment{}
		if err = jsonpb.UnmarshalString(string(comment.Comment), &tcomment); err != nil {
			return nil, err
		}
		selections[i].Included = isChanged && !isSuppressed
	}

	return selections, nil
}

// collectComments collects the comments in the results from the analyzer.
//
// Either isolatedNamespace and isolatedOutputHash, or buildbucketOutput,
// should be populated.
func collectComments(c context.Context, isolator common.IsolateAPI, isolateServerURL, isolatedNamespace, isolatedOutputHash, buildbucketOutput, analyzerName string, workerKey *ds.Key) ([]*track.Comment, error) {
	var comments []*track.Comment
	results := tricium.Data_Results{}
	// If isolate is present, fetch the data. Otherwise, unmarshal the
	// buildbucket output.
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

// suppressedCategories returns the categories of all comments that have been
// reported as not useful for a given Gerrit CL.
//
// This is a potentially expensive operation; it requires
//   (1) querying runs (AnalyzeRequests) for a given Gerrit change
//   (2) querying descendant CommentFeedback for each run with not useful reports
//   (3) getting all relevant comments, including comment category.
//
// In the case of an error, this function will only log an error and
// return an empty set.
func suppressedCategories(c context.Context, host, change string) stringset.Set {
	comments, err := fetchNotUsefulComments(c, host, change)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to fetch past not useful comments.")
		return stringset.NewFromSlice()
	}
	categories := stringset.New(len(comments))
	for _, comment := range comments {
		categories.Add(comment.Category)
	}
	return categories
}

// fetchNotUsefulComments returns all comments for a given CL that have had
// not-useful feedback.
func fetchNotUsefulComments(c context.Context, host, change string) ([]*track.Comment, error) {
	// Each AnalyzeRequest key represents one run, usually one for each
	// patchset.
	arKeys, err := fetchRequestKeysByChange(c, host, change)
	if err != nil {
		return nil, err
	}
	// In order to get only comments with "not useful" reports, we do a
	// query for CommentFeedback keys.
	cfKeys, err := fetchAllCommentFeedback(c, arKeys)
	if err != nil {
		return nil, err
	}
	// The parents of those CommentFeedback entities are the comments we're
	// interested in.
	var comments []*track.Comment
	for _, k := range cfKeys {
		comments = append(comments, &track.Comment{
			Parent: k.Parent().Parent(),
			ID:     k.Parent().IntID(),
		})
	}
	err = ds.Get(c, comments)
	return comments, err
}

// fetchRequestKeysByChange returns keys for all AnalyzeRequest entities that
// are for one particular CL.
func fetchRequestKeysByChange(c context.Context, host, change string) ([]*ds.Key, error) {
	// If an empty string is passed, there is no Gerrit change to match.
	if host == "" || change == "" {
		return nil, errors.Reason("unexpectedly got an empty host or change").Err()
	}
	q := ds.NewQuery("AnalyzeRequest").Eq("GerritHost", host).Eq("GerritChange", change)
	var keys []*ds.Key
	if err := ds.GetAll(c, q.KeysOnly(true), &keys); err != nil {
		return nil, errors.Annotate(err, "failed to get AnalyzeRequest keys").Err()
	}
	return keys, nil
}

// FetchAllCommentFeedback fetches keys of CommentFeedback entities
// that have at least one "not useful" report.
//
// This does multiple ancestor queries in parallel for some number of
// AnalyzeRequest keys, and returns the keys of all CommentFeedback entities
// with "not useful" reports.
func fetchAllCommentFeedback(c context.Context, arKeys []*ds.Key) ([]*ds.Key, error) {
	// There will be multiple queries running in different goroutines, and
	// appending them to a single slice is not threadsafe. By making a 2D
	// slice, we can add keys for each AnalyzeRequest without conflict.
	cfKeys := make([][]*ds.Key, len(arKeys))

	// It's possible that too many parallel requests will result in some
	// aborting due to timeout. Hard-limiting number of parallel requests
	// may help with this.
	if err := parallel.WorkPool(8, func(taskC chan<- func() error) {
		for i, arKey := range arKeys {
			ancestor := arKey // Declare a new variable for the closure below.
			taskC <- func() error {
				q := ds.NewQuery("CommentFeedback").Ancestor(ancestor).Gt("NotUsefulReports", 0)
				err := ds.GetAll(c, q.KeysOnly(true), &cfKeys[i])
				return err
			}
		}
	}); err != nil {
		return nil, errors.Annotate(err, "failed to fetch CommentFeedback keys").Err()
	}

	// The CommentFeedback keys must be flattened before returning.
	var ret []*ds.Key
	for _, keys := range cfKeys {
		ret = append(ret, keys...)
	}
	return ret, nil
}
