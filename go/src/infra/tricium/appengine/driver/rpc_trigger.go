// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"encoding/base64"
	"fmt"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
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
	if err := trigger(c, req, config.WorkflowCache, common.SwarmingServer, common.IsolateServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to trigger worker: %v", err)
	}
	return &admin.TriggerResponse{}, nil
}

func trigger(c context.Context, req *admin.TriggerRequest, wp config.WorkflowCacheAPI, sw common.SwarmingAPI, isolator common.IsolateAPI) error {
	workflow, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	worker, err := workflow.GetWorker(req.Worker)
	if err != nil {
		return fmt.Errorf("unknown worker in workflow, worker: %s", worker.Name)
	}
	tags := swarmingTags(c, req.Worker, req.RunId)
	// TODO(emso): Auth check.
	// TODO(emso): Runtime type check.
	workerIsolate, err := isolator.IsolateWorker(c, workflow.IsolateServer, worker, req.IsolatedInputHash)
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
	taskID, err := sw.Trigger(c, workflow.SwarmingServer, workflow.IsolateServer, worker, workerIsolate, userdata, tags)
	if err != nil {
		return fmt.Errorf("failed to call trigger on swarming API: %v", err)
	}
	// Mark worker as launched.
	b, err = proto.Marshal(&admin.WorkerLaunchedRequest{
		RunId:             req.RunId,
		Worker:            req.Worker,
		IsolatedInputHash: req.IsolatedInputHash,
		SwarmingTaskId:    taskID,
	})
	if err != nil {
		return fmt.Errorf("failed to encode worker launched request: %v", err)
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-launched", nil)
	t.Payload = b
	return tq.Add(c, common.TrackerQueue, t)
}

// swarmingTags generates tags to send when triggering tasks.
//
// These tags can be used later when querying tasks, so
// any attribute of a job that we may want to query or filter
// by could be added as a tag.
func swarmingTags(c context.Context, worker string, runID int64) []string {
	function, platform, err := track.ExtractFunctionPlatform(worker)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to split worker name: %s", worker)
		return nil
	}
	tags := []string{
		"tricium:1",
		"function:" + function,
		"platform:" + platform,
	}
	// Add Gerrit details if applicable.
	request := &track.AnalyzeRequest{ID: runID}
	if err := ds.Get(c, request); err != nil {
		logging.WithError(err).Errorf(c, "failed to get request for run ID: %d", runID)
		return tags
	}
	if request.Consumer == tricium.Consumer_GERRIT {
		cl, patch := common.ExtractCLPatchSetNumbers(request.GerritRevision)
		tags = append(tags,
			"gerrit_project:"+request.GerritProject,
			"gerrit_change:"+request.GerritChange,
			"gerrit_cl_number:"+cl,
			"gerrit_patch_set:"+patch,
		)
	}
	return tags
}
