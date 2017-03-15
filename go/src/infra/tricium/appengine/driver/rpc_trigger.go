// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"encoding/base64"
	"fmt"

	"github.com/golang/protobuf/proto"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

// DriverServer represents the Tricium pRPC Driver server.
type driverServer struct{}

var server = &driverServer{}

// Trigger triggers processes one trigger request to the Tricium driver.
func (*driverServer) Trigger(c context.Context, req *admin.TriggerRequest) (*admin.TriggerResponse, error) {
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if req.Worker == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing worker name")
	}
	if req.IsolatedInputHash == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing isolated input hash")
	}
	if err := trigger(c, req, &common.DatastoreWorkflowConfigProvider{},
		&common.SwarmingServer{
			SwarmingServerURL: req.SwarmingServerUrl,
			IsolateServerURL:  req.IsolateServerUrl,
		}, &common.IsolateServer{IsolateServerURL: req.IsolateServerUrl}); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to trigger worker: %v", err)
	}
	return &admin.TriggerResponse{}, nil
}

func trigger(c context.Context, req *admin.TriggerRequest, wp common.WorkflowProvider, sw common.SwarmingAPI, isolator common.Isolator) error {
	workflow, err := wp.ReadConfigForRun(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	worker, err := workflow.GetWorker(req.Worker)
	if err != nil {
		return fmt.Errorf("unknown worker in workflow, worker: %s", worker.Name)
	}
	// TODO(emso): Auth check.
	// TODO(emso): Runtime type check.
	workerIsolate, err := isolator.IsolateWorker(c, worker, req.IsolatedInputHash)
	if err != nil {
		return fmt.Errorf("failed to isolate command for trigger: %v", err)
	}
	logging.Infof(c, "[driver] Created worker isolate, hash: %q", workerIsolate)
	// Create PubSub userdata for trigger request.
	b, err := proto.Marshal(req)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to marshal trigger request for PubSub user data: %v", err)
		return fmt.Errorf("failed to marshal PubSub user data for swarming task: %v", err)
	}
	userdata := base64.StdEncoding.EncodeToString(b)
	logging.Infof(c, "[driver] PubSub userdata for trigger: %q", userdata)
	// Trigger worker.
	taskID, err := sw.Trigger(c, worker, workerIsolate, userdata, workflow.WorkerTopic)
	if err != nil {
		return fmt.Errorf("failed to call trigger on swarming API: %v", err)
	}
	// Mark worker as launched.
	b, err = proto.Marshal(&admin.WorkerLaunchedRequest{
		RunId:             req.RunId,
		Worker:            req.Worker,
		IsolateServerUrl:  req.IsolateServerUrl,
		IsolatedInputHash: req.IsolatedInputHash,
		SwarmingServerUrl: req.SwarmingServerUrl,
		TaskId:            taskID,
	})
	if err != nil {
		return fmt.Errorf("failed to encode worker launched request: %v", err)
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-launched", nil)
	t.Payload = b
	return tq.Add(c, common.TrackerQueue, t)
}
