// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// trackerServer represents the Tricium pRPC Tracker service.
type trackerServer struct{}

// WorkflowLaunched tracks the launch of a workflow.
func (*trackerServer) WorkflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest) (res *admin.WorkflowLaunchedResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"runID": req.RunId,
	}.Infof(c, "Received workflow launched request.")
	if req.RunId == 0 {
		return nil, errors.Reason("missing run ID").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	if err := workflowLaunched(c, req, config.WorkflowCache); err != nil {
		return nil, errors.Annotate(err, "failed to track workflow launched").Tag(grpcutil.InternalTag).Err()
	}
	return &admin.WorkflowLaunchedResponse{}, nil
}

func workflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest, wp config.WorkflowCacheAPI) error {
	wf, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return errors.Annotate(err, "failed to read workflow config").Err()
	}
	// Prepare function and worker invocation tracking entries to store.
	fw, functions := extractFunctionWorkerStructure(c, wf)

	// In most cases, when a workflow is launched, we update the state of
	// the workflow and the analyze request to RUNNING.
	newState := tricium.State_RUNNING

	// However, if there are no functions (rare edge case), then the workflow
	// is trivially considered "done" and is marked as such immediately.
	if len(fw) == 0 && len(functions) == 0 {
		if err != nil {
			return errors.Annotate(err, "failed to read workflow config").Err()
		}
		logging.Warningf(c, "No functions found in workflow, nothing to do")
		newState = tricium.State_SUCCESS
	}

	logging.Debugf(c, "Extracted function/worker entries for tracking: %#v", fw)
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Store the root of the workflow.
		workflowRun := &track.WorkflowRun{
			ID:                    1,
			Parent:                requestKey,
			IsolateServerURL:      wf.IsolateServer,
			SwarmingServerURL:     wf.SwarmingServer,
			BuildbucketServerHost: wf.BuildbucketServerHost,
			Functions:             functions,
		}
		if err := ds.Put(c, workflowRun); err != nil {
			return errors.Reason("failed to store WorkflowRun entity (run ID: %d): %v", req.RunId, err).Err()
		}
		runKey := ds.KeyForObj(c, workflowRun)
		return parallel.FanOutIn(func(taskC chan<- func() error) {

			// Update AnalyzeRequestResult.
			taskC <- func() error {
				r := &track.AnalyzeRequestResult{
					ID:     1,
					Parent: requestKey,
					State:  newState,
				}
				if err := ds.Put(c, r); err != nil {
					return errors.Annotate(err, "failed to mark request as launched").Err()
				}
				return nil
			}

			// Update WorkflowRunResult.
			taskC <- func() error {
				r := &track.WorkflowRunResult{
					ID:     1,
					Parent: runKey,
					State:  newState,
				}
				if err := ds.Put(c, r); err != nil {
					return errors.Annotate(err, "failed to mark workflow as launched").Err()
				}
				return nil
			}

			// Store Function and WorkerRun entities for tracking.
			taskC <- func() error {
				entities := make([]interface{}, 0, len(fw))
				for _, v := range fw {
					v.Function.Parent = runKey
					if fd := tricium.LookupFunction(wf.Functions, v.Function.ID); fd != nil {
						v.Function.Owner = fd.Owner
						v.Function.MonorailComponent = fd.MonorailComponent
					}
					functionKey := ds.KeyForObj(c, v.Function)
					entities = append(entities, []interface{}{
						v.Function,
						&track.FunctionRunResult{
							ID:     1,
							Parent: functionKey,
							Name:   v.Function.ID,
							State:  tricium.State_PENDING,
						},
					}...)
					for _, worker := range v.Workers {
						worker.Parent = functionKey
						entities = append(entities, worker)
						workerKey := ds.KeyForObj(c, worker)
						entities = append(entities, []interface{}{
							worker,
							&track.WorkerRunResult{
								ID:       1,
								Name:     worker.ID,
								Function: v.Function.ID,
								Parent:   workerKey,
								State:    tricium.State_PENDING,
							},
						}...)
					}
				}
				if err := ds.Put(c, entities); err != nil {
					return errors.Annotate(err, "failed to store function and worker entities").Err()
				}
				return nil
			}
		})
	}, nil); err != nil {
		return err
	}
	return nil
}

type functionRunWorkers struct {
	Function *track.FunctionRun
	Workers  []*track.WorkerRun
}

// extractFunctionWorkerStructure extracts a map of function names to
// functionRunWorkers structures from a workflow config.
func extractFunctionWorkerStructure(
	c context.Context, wf *admin.Workflow) (map[string]*functionRunWorkers, []string) {
	m := map[string]*functionRunWorkers{}
	var functions []string
	for _, w := range wf.Workers {
		function, _, err := track.ExtractFunctionPlatform(w.Name)
		if err != nil {
			logging.WithError(err).Errorf(c, "Failed to extract function name")
		}
		a, ok := m[function]
		if !ok {
			a = &functionRunWorkers{Function: &track.FunctionRun{ID: function}}
			m[function] = a
		}
		workerRun := &track.WorkerRun{ID: w.Name, Platform: w.ProvidesForPlatform}
		for _, n := range w.Next {
			workerRun.Next = append(workerRun.Next, n)
		}
		a.Workers = append(a.Workers, workerRun)
		a.Function.Workers = append(a.Function.Workers, w.Name)
		functions = append(functions, function)
		logging.Debugf(c, "Found function %q with %d workers", function, len(a.Workers))
	}
	return m, functions
}
