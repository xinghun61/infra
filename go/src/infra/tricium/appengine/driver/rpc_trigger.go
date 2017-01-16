// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"fmt"

	"github.com/golang/protobuf/proto"
	tq "github.com/luci/gae/service/taskqueue"

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
	if err := trigger(c, req, &common.DatastoreConfigProvider{}); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to trigger worker: %v", err)
	}
	return &admin.TriggerResponse{}, nil
}

func trigger(c context.Context, req *admin.TriggerRequest, wp common.WorkflowProvider) error {
	_, err := wp.ReadConfigForRun(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	// TODO(emso): Auth check.
	// TODO(emso): Runtime type check.
	// TODO(emso): Isolate swarming input.
	// TODO(emso): Launch swarming task and get actual task URL. Put
	// runID, worker name, and hash tp isolated input in pubsub userdata.
	swarmingURL := "https://chromium-swarm-dev.appspot.com"
	taskID := "123456789"
	// Mark worker as launched.
	b, err := proto.Marshal(&admin.WorkerLaunchedRequest{
		RunId:             req.RunId,
		Worker:            req.Worker,
		IsolatedInputHash: req.IsolatedInputHash,
		SwarmingUrl:       swarmingURL,
		TaskId:            taskID,
	})
	if err != nil {
		return fmt.Errorf("failed to encode worker launched request: %v", err)
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-launched", nil)
	t.Payload = b
	return tq.Add(c, common.TrackerQueue, t)
}
