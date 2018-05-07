// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"fmt"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// WorkerLaunched tracks the launch of a worker.
func (*trackerServer) WorkerLaunched(c context.Context, req *admin.WorkerLaunchedRequest) (*admin.WorkerLaunchedResponse, error) {
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if req.Worker == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing worker")
	}
	if req.IsolatedInputHash == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolated input hash")
	}
	if req.SwarmingTaskId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing swarming task ID")
	}
	if err := workerLaunched(c, req); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track worker launched: %v", err)
	}
	return &admin.WorkerLaunchedResponse{}, nil
}

func workerLaunched(c context.Context, req *admin.WorkerLaunchedRequest) error {
	logging.Debugf(c, "[tracker] Worker launched (run ID: %d, worker: %s, taskID: %s, IsolatedInput: %s)", req.RunId, req.Worker, req.SwarmingTaskId, req.IsolatedInputHash)
	// Compute needed keys.
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	name, _, err := track.ExtractFunctionPlatform(req.Worker)
	if err != nil {
		return fmt.Errorf("failed to extract function name: %v", err)
	}
	functionRunKey := ds.NewKey(c, "FunctionRun", name, 0, runKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, functionRunKey)
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		return parallel.FanOutIn(func(taskC chan<- func() error) {
			// Update worker state to launched.
			taskC <- func() error {
				wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
				if err := ds.Get(c, wr); err != nil {
					return fmt.Errorf("failed to get WorkerRunResult: %v", err)
				}
				if wr.State == tricium.State_PENDING {
					wr.State = tricium.State_RUNNING
					wr.IsolatedInput = req.IsolatedInputHash
					wr.SwarmingTaskID = req.SwarmingTaskId
					if err := ds.Put(c, wr); err != nil {
						return fmt.Errorf("failed to update WorkerRunResult: %v", err)
					}
				} else {
					logging.Warningf(c, "worker not in PENDING state when launched, run.ID: %d, worker: %s", req.RunId, req.Worker)
				}
				return nil
			}

			// Update function state to launched if necessary.
			taskC <- func() error {
				fr := &track.FunctionRunResult{ID: 1, Parent: functionRunKey}
				if err := ds.Get(c, fr); err != nil {
					return fmt.Errorf("failed to get FunctionRunResult: %v", err)
				}
				if fr.State == tricium.State_PENDING {
					fr.State = tricium.State_RUNNING
					if err := ds.Put(c, fr); err != nil {
						return fmt.Errorf("failed to update FunctionRunResult to launched: %v", err)
					}
				}
				return nil
			}
		})
	}, nil); err != nil {
		return nil
	}
	// Notify reporter.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return fmt.Errorf("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err)
	}
	switch request.Consumer {
	case tricium.Consumer_GERRIT:
		// TODO(emso): push notification to the Gerrit reporter
	default:
		// Do nothing.
	}
	return nil
}
