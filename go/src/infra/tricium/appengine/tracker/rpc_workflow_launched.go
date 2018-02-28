// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"fmt"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// TrackerServer represents the Tricium pRPC Tracker server.
type trackerServer struct{}

var server = &trackerServer{}

// WorkflowLaunched tracks the launch of a workflow.
func (*trackerServer) WorkflowLaunched(
	c context.Context, req *admin.WorkflowLaunchedRequest) (*admin.WorkflowLaunchedResponse, error) {
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := workflowLaunched(c, req, config.WorkflowCache); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track workflow launched: %v", err)
	}
	return &admin.WorkflowLaunchedResponse{}, nil
}

func workflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest, wp config.WorkflowCacheAPI) error {
	wf, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	// Prepare function and worker invocation tracking entries to store.
	fw, functions := extractFunctionWorkerStructure(c, wf)
	logging.Debugf(c, "Extracted function/worker entries for tracking: %#v", fw)
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Store the root of the workflow.
		workflowRun := &track.WorkflowRun{
			ID:                1,
			Parent:            requestKey,
			IsolateServerURL:  wf.IsolateServer,
			SwarmingServerURL: wf.SwarmingServer,
			Functions:         functions,
		}
		if err := ds.Put(c, workflowRun); err != nil {
			return fmt.Errorf("failed to store WorkflowRun entity (run ID: %d): %v", req.RunId, err)
		}
		runKey := ds.KeyForObj(c, workflowRun)
		ops := []func() error{
			// Update AnalyzeRequestResult to RUNNING.
			func() error {
				r := &track.AnalyzeRequestResult{
					ID:     1,
					Parent: requestKey,
					State:  tricium.State_RUNNING,
				}
				if err := ds.Put(c, r); err != nil {
					return fmt.Errorf("failed to mark request as launched: %v", err)
				}
				return nil
			},
			// Update WorkflowRun state to RUNNING.
			func() error {
				r := &track.WorkflowRunResult{
					ID:     1,
					Parent: runKey,
					State:  tricium.State_RUNNING,
				}
				if err := ds.Put(c, r); err != nil {
					return fmt.Errorf("failed to mark workflow as launched: %v", err)
				}
				return nil
			},
			// Store Function and WorkerRun entities for tracking.
			func() error {
				entities := make([]interface{}, 0, len(fw))
				for _, v := range fw {
					v.Function.Parent = runKey
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
					return fmt.Errorf("failed to store function and worker entities: %v", err)
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
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
			logging.Errorf(c, "Failed to extract function name: %v", err)
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
		logging.Debugf(c, "Found function/worker: %v", a)
	}
	return m, functions
}
