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
	"infra/tricium/appengine/common/track"
)

// WorkerLaunched tracks the launch of a worker.
func (*trackerServer) WorkerLaunched(c context.Context, req *admin.WorkerLaunchedRequest) (res *admin.WorkerLaunchedResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	if req.RunId == 0 {
		return nil, errors.New("missing run ID", grpcutil.InvalidArgumentTag)
	}
	if req.Worker == "" {
		return nil, errors.New("missing worker", grpcutil.InvalidArgumentTag)
	}
	if req.IsolatedInputHash == "" {
		return nil, errors.New("missing isolated input hash", grpcutil.InvalidArgumentTag)
	}
	if req.SwarmingTaskId == "" && req.BuildbucketBuildId == 0 {
		return nil, errors.New("missing swarming task and buildbucket ID, one must be present", grpcutil.InvalidArgumentTag)
	}
	if req.SwarmingTaskId != "" && req.BuildbucketBuildId != 0 {
		return nil, errors.New("have both swarming and buildbucket IDs, only one can be present", grpcutil.InvalidArgumentTag)
	}
	if err := workerLaunched(c, req); err != nil {
		return nil, errors.Annotate(err, "failed to track worker launched").
			Tag(grpcutil.InternalTag).Err()
	}
	return &admin.WorkerLaunchedResponse{}, nil
}

func workerLaunched(c context.Context, req *admin.WorkerLaunchedRequest) error {
	logging.Fields{
		"runID":         req.RunId,
		"worker":        req.Worker,
		"taskID":        req.SwarmingTaskId,
		"buildID":       req.BuildbucketBuildId,
		"isolatedInput": req.IsolatedInputHash,
	}.Infof(c, "Request received.")
	// Compute needed keys.
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
	name, _, err := track.ExtractFunctionPlatform(req.Worker)
	if err != nil {
		return errors.Annotate(err, "failed to extract function name").Err()
	}
	functionRunKey := ds.NewKey(c, "FunctionRun", name, 0, runKey)
	workerKey := ds.NewKey(c, "WorkerRun", req.Worker, 0, functionRunKey)
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		return parallel.FanOutIn(func(taskC chan<- func() error) {
			// Update worker state to launched.
			taskC <- func() error {
				wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
				if err := ds.Get(c, wr); err != nil {
					return errors.Annotate(err, "failed to get WorkerRunResult").Err()
				}
				if wr.State == tricium.State_PENDING {
					wr.State = tricium.State_RUNNING
					wr.IsolatedInput = req.IsolatedInputHash
					wr.SwarmingTaskID = req.SwarmingTaskId
					wr.BuildbucketBuildID = req.BuildbucketBuildId
					if err := ds.Put(c, wr); err != nil {
						return errors.Annotate(err, "failed to update WorkerRunResult").Err()
					}
				} else {
					logging.Fields{
						"runID":  req.RunId,
						"worker": req.Worker,
					}.Warningf(c, "Worker not in PENDING state when launched.")
				}
				return nil
			}

			// Update function state to launched if necessary.
			taskC <- func() error {
				fr := &track.FunctionRunResult{ID: 1, Parent: functionRunKey}
				if err := ds.Get(c, fr); err != nil {
					return errors.Annotate(err, "failed to get FunctionRunResult").Err()
				}
				if fr.State == tricium.State_PENDING {
					fr.State = tricium.State_RUNNING
					if err := ds.Put(c, fr); err != nil {
						return errors.Annotate(err, "failed to update FunctionRunResult to launched").Err()
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
		return errors.Annotate(err, "failed to get AnalyzeRequest entity (run ID: %d)", req.RunId).Err()
	}
	return nil
}
