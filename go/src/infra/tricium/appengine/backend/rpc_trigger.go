// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"encoding/base64"
	"fmt"
	"strconv"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/gerrit"
	"infra/tricium/appengine/common/track"
)

// DriverServer represents the Tricium pRPC Driver server.
type driverServer struct{}

// Trigger triggers processes one trigger request to the Tricium driver.
func (*driverServer) Trigger(c context.Context, req *admin.TriggerRequest) (*admin.TriggerResponse, error) {
	if req.RunId == 0 {
		return nil, errors.New("missing run ID", grpcutil.InvalidArgumentTag)
	}
	if req.Worker == "" {
		return nil, errors.New("missing worker name", grpcutil.InvalidArgumentTag)
	}
	if req.IsolatedInputHash == "" {
		return nil, errors.New("missing isolated input hash", grpcutil.InvalidArgumentTag)
	}
	if err := trigger(c, req, config.WorkflowCache, common.SwarmingServer, common.BuildbucketServer, common.IsolateServer); err != nil {
		return nil, errors.Annotate(err, "failed to trigger worker").
			Tag(grpcutil.InternalTag).Err()
	}
	return &admin.TriggerResponse{}, nil
}

func trigger(c context.Context, req *admin.TriggerRequest, wp config.WorkflowCacheAPI, sw, bb common.TaskServerAPI, isolator common.IsolateAPI) error {
	workflow, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return errors.Annotate(err, "failed to read workflow config").Err()
	}
	worker, err := workflow.GetWorker(req.Worker)
	if err != nil {
		return errors.Annotate(err, "failed to get worker %q", req.Worker).Err()
	}
	patch := fetchPatchDetails(c, req.RunId)
	tags := getTags(c, req.Worker, req.RunId, patch)

	// Create PubSub userdata for trigger request.
	b, err := proto.Marshal(req)
	if err != nil {
		return errors.Annotate(err, "failed to marshal PubSub user data for swarming task").Err()
	}
	userdata := base64.StdEncoding.EncodeToString(b)
	logging.Fields{
		"userdata": userdata,
	}.Infof(c, "PubSub userdata created.")

	result := &common.TriggerResult{}
	switch wi := worker.Impl.(type) {
	case *admin.Worker_Recipe:
		// Trigger worker.
		result, err = bb.Trigger(c, &common.TriggerParameters{
			Server:           workflow.BuildbucketServerHost,
			IsolateServerURL: workflow.IsolateServer,
			Worker:           worker,
			PubsubUserdata:   userdata,
			Tags:             tags,
			Patch:            patch,
		})
		if err != nil {
			return errors.Annotate(err, "failed to call trigger on buildbucket API").Err()
		}
	case *admin.Worker_Cmd:
		workerIsolate, err := isolator.IsolateWorker(c, workflow.IsolateServer, worker, req.IsolatedInputHash)
		if err != nil {
			return errors.Annotate(err, "failed to isolate command for trigger").Err()
		}
		logging.Fields{
			"workerIsolate": workerIsolate,
		}.Infof(c, "Created worker isolate.")
		// Trigger worker.
		result, err = sw.Trigger(c, &common.TriggerParameters{
			Server:           workflow.SwarmingServer,
			IsolateServerURL: workflow.IsolateServer,
			Worker:           worker,
			WorkerIsolate:    workerIsolate,
			PubsubUserdata:   userdata,
			Tags:             tags,
		})
		if err != nil {
			return errors.Annotate(err, "failed to call trigger on swarming API").Err()
		}
	case nil:
		return errors.Reason("missing Impl when isolating worker %s", worker.Name).Err()
	default:
		return errors.Reason("Impl.Impl has unexpected type %T", wi).Err()
	}
	// Mark worker as launched.
	b, err = proto.Marshal(&admin.WorkerLaunchedRequest{
		RunId:              req.RunId,
		Worker:             req.Worker,
		IsolatedInputHash:  req.IsolatedInputHash,
		SwarmingTaskId:     result.TaskID,
		BuildbucketBuildId: result.BuildID,
	})
	if err != nil {
		return errors.Annotate(err, "failed to encode worker launched request").Err()
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-launched", nil)
	t.Payload = b
	return tq.Add(c, common.TrackerQueue, t)
}

// getTags generates tags to send when triggering tasks via buildbucket or swarming.
//
// These tags can be used later when querying tasks, so
// any attribute of a job that we may want to query or filter
// by could be added as a tag.
func getTags(c context.Context, worker string, runID int64, patch common.PatchDetails) []string {
	function, platform, err := track.ExtractFunctionPlatform(worker)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to split worker name: %s", worker)
		return nil
	}
	tags := []string{
		"function:" + function,
		"platform:" + platform,
		"run_id:" + strconv.FormatInt(runID, 10),
		"tricium:1",
	}
	if patch.GerritProject != "" {
		tags = append(tags,
			"gerrit_project:"+patch.GerritProject,
			"gerrit_change:"+patch.GerritChange,
			"gerrit_cl_number:"+patch.GerritCl,
			"gerrit_patch_set:"+patch.GerritPatch,
			fmt.Sprintf("buildset:patch/gerrit/%s/%s/%s", patch.GerritHost, patch.GerritCl, patch.GerritPatch),
		)
	}
	return tags
}

func fetchPatchDetails(c context.Context, runID int64) common.PatchDetails {
	var patch common.PatchDetails
	request := &track.AnalyzeRequest{ID: runID}
	if err := ds.Get(c, request); err != nil {
		logging.WithError(err).Errorf(c, "Failed to get request for run ID: %d", runID)
		return patch
	}
	patch.GitilesHost = request.GitURL
	patch.GitilesProject = request.Project
	if request.GerritProject != "" && request.GerritChange != "" {
		cl, p := gerrit.ExtractCLPatchSetNumbers(request.GitRef)
		patch.GerritHost = request.GerritHost
		patch.GerritProject = request.GerritProject
		patch.GerritChange = request.GerritChange
		patch.GerritCl = cl
		patch.GerritPatch = p
	}
	return patch
}
