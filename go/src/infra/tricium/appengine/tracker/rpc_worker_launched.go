// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"fmt"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
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
	if req.IsolateServerUrl == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolate server URL")
	}
	if req.IsolatedInputHash == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolated input hash")
	}
	if req.SwarmingServerUrl == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing swarming URL")
	}
	if req.TaskId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing swarming task ID")
	}
	if err := workerLaunched(c, req); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track worker launched: %v", err)
	}
	return &admin.WorkerLaunchedResponse{}, nil
}

func workerLaunched(c context.Context, req *admin.WorkerLaunchedRequest) error {
	logging.Infof(c, "[tracker] Worker launched (run ID: %d, worker: %s, taskID: %s, IsolatedInput: %s)", req.RunId, req.Worker, req.TaskId, req.IsolatedInputHash)
	_, analyzerKey, workerKey := createKeys(c, req.RunId, req.Worker)
	logging.Infof(c, "[tracker] Looking up worker, key: %s", workerKey)
	run := &track.Run{ID: req.RunId}
	if err := ds.Get(c, run); err != nil {
		return fmt.Errorf("failed to retrieve run entry (run ID: %d): %v", run.ID, err)
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
			// Update worker state to launched.
			func() error {
				w := &track.WorkerInvocation{
					ID:     workerKey.StringID(),
					Parent: workerKey.Parent(),
				}
				if err := ds.Get(c, w); err != nil {
					return fmt.Errorf("failed to retrieve worker: %v", err)
				}
				w.State = tricium.State_RUNNING
				w.IsolateServerURL = req.IsolateServerUrl
				w.IsolatedInput = req.IsolatedInputHash
				w.TaskID = req.TaskId
				w.SwarmingURL = req.SwarmingServerUrl
				if err := ds.Put(c, w); err != nil {
					return fmt.Errorf("failed to mark worker as launched: %v", err)
				}
				return nil
			},
			// Maybe update analyzer state to launched.
			func() error {
				a := &track.AnalyzerInvocation{
					ID:     analyzerKey.StringID(),
					Parent: analyzerKey.Parent(),
				}
				if err := ds.Get(c, a); err != nil {
					return fmt.Errorf("failed to retrieve analyzer: %v", err)
				}
				if a.State == tricium.State_PENDING {
					a.State = tricium.State_RUNNING
					if err := ds.Put(c, a); err != nil {
						return fmt.Errorf("failed to mark analyzer as launched: %v", err)
					}
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
	}, nil)
}
