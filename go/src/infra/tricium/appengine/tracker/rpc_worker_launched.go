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
	return ds.RunInTransaction(c, func(c context.Context) (err error) {
		done := make(chan error)
		defer func() {
			if err2 := <-done; err == nil {
				err = err2
			}
		}()
		// Update worker state, set to launched.
		go func() {
			w := &track.WorkerInvocation{
				ID:     workerKey.StringID(),
				Parent: workerKey.Parent(),
			}
			if err := ds.Get(c, w); err != nil {
				done <- fmt.Errorf("failed to retrieve worker: %v", err)
				return
			}
			w.State = track.Launched
			w.IsolateServerURL = req.IsolateServerUrl
			w.IsolatedInput = req.IsolatedInputHash
			w.TaskID = req.TaskId
			w.SwarmingURL = req.SwarmingServerUrl
			if err := ds.Put(c, w); err != nil {
				done <- fmt.Errorf("failed to mark worker as launched: %v", err)
				return
			}
			done <- nil
		}()
		// Maybe update analyzer state, set to launched.
		a := &track.AnalyzerInvocation{
			ID:     analyzerKey.StringID(),
			Parent: analyzerKey.Parent(),
		}
		if err := ds.Get(c, a); err != nil {
			return fmt.Errorf("failed to retrieve analyzer: %v", err)
		}
		if a.State == track.Pending {
			a.State = track.Launched
			if err := ds.Put(c, a); err != nil {
				return fmt.Errorf("failed to mark analyzer as launched: %v", err)
			}
		}
		return nil
	}, nil)
}
