// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"fmt"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

// Collect processes one collect request to the Tricium driver.
func (*driverServer) Collect(c context.Context, req *admin.CollectRequest) (*admin.CollectResponse, error) {
	logging.Infof(c, "[driver]: Received collect request (run ID: %d, worker: %s, task ID: %s)", req.RunId, req.Worker, req.TaskId)
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if req.Worker == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing worker name")
	}
	if req.IsolatedInputHash == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolated input hash")
	}
	if err := collect(c, req, config.DatastoreWorkflowProvider,
		&common.SwarmingServer{
			SwarmingServerURL: req.SwarmingServerUrl,
			IsolateServerURL:  req.IsolateServerUrl,
		},
		&common.IsolateServer{IsolateServerURL: req.IsolateServerUrl}); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to trigger worker: %v", err)
	}
	return &admin.CollectResponse{}, nil
}

func collect(c context.Context, req *admin.CollectRequest, wp config.WorkflowProvider, sw common.SwarmingAPI, isolator common.Isolator) error {
	wf, err := wp.ReadWorkflowForRun(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}

	isolatedOutput, exitCode, err := sw.Collect(c, req.TaskId)
	if err != nil {
		return fmt.Errorf("failed to collect swarming task result: %v", err)
	}

	// Mark worker as done.
	b, err := proto.Marshal(&admin.WorkerDoneRequest{
		RunId:              req.RunId,
		Worker:             req.Worker,
		IsolateServerUrl:   req.IsolateServerUrl,
		IsolatedOutputHash: isolatedOutput,
		ExitCode:           exitCode,
	})
	if err != nil {
		return fmt.Errorf("failed to encode worker done request: %v", err)
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-done", nil)
	t.Payload = b
	if err := tq.Add(c, common.TrackerQueue, t); err != nil {
		return fmt.Errorf("failed to enqueue track request: %v", err)
	}

	// Create layered isolated input, include the input in the collect request and
	// massage the isolated output into new isolated input.
	isolatedInput, err := isolator.LayerIsolates(c, req.IsolatedInputHash, isolatedOutput)
	if err != nil {
		return fmt.Errorf("failed layer isolates: %v", err)
	}

	// Enqueue trigger requests for successors.
	for _, worker := range wf.GetNext(req.Worker) {
		b, err := proto.Marshal(&admin.TriggerRequest{
			RunId:             req.RunId,
			IsolateServerUrl:  req.IsolateServerUrl,
			IsolatedInputHash: isolatedInput,
			SwarmingServerUrl: req.SwarmingServerUrl,
			Worker:            worker,
		})
		if err != nil {
			return fmt.Errorf("failed to marshal successor trigger request: %v", err)
		}
		t := tq.NewPOSTTask("/driver/internal/trigger", nil)
		t.Payload = b
		if err := tq.Add(c, common.DriverQueue, t); err != nil {
			return fmt.Errorf("failed to enqueue collect request: %v", err)
		}
	}
	return nil
}
