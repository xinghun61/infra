// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"github.com/golang/protobuf/proto"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

// Collect processes one collect request to the Tricium driver.
func (*driverServer) Collect(c context.Context, req *admin.CollectRequest) (res *admin.CollectResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"run ID":  req.RunId,
		"worker":  req.Worker,
		"task ID": req.TaskId,
	}.Infof(c, "[driver] Collect request received.")
	if err := validateCollectRequest(req); err != nil {
		return nil, errors.Annotate(err, "invalid request").
			Tag(grpcutil.InvalidArgumentTag).Err()
	}

	if err := collect(c, req, config.WorkflowCache, common.SwarmingServer, common.BuildbucketServer, common.IsolateServer); err != nil {
		return nil, err
	}
	return &admin.CollectResponse{}, nil
}

func validateCollectRequest(req *admin.CollectRequest) error {
	if req.RunId == 0 {
		return errors.New("missing run ID")
	}
	if req.Worker == "" {
		return errors.New("missing worker name")
	}
	return nil
}

func collect(c context.Context, req *admin.CollectRequest,
	wp config.WorkflowCacheAPI, sw, bb common.TaskServerAPI, isolator common.IsolateAPI) error {
	wf, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return errors.Annotate(err, "failed to read workflow config").Err()
	}
	w, err := wf.GetWorker(req.Worker)
	if err != nil {
		return errors.Annotate(err, "failed to get worker").Err()
	}

	result := &common.CollectResult{}
	switch wi := w.Impl.(type) {
	case *admin.Worker_Recipe:
		result, err = bb.Collect(c, &common.CollectParameters{
			Server:  wf.BuildbucketServerHost,
			BuildID: req.BuildId,
		})
		if err != nil {
			return errors.Annotate(err, "failed to collect task").Err()
		}
	case *admin.Worker_Cmd:
		result, err = sw.Collect(c, &common.CollectParameters{
			Server: wf.SwarmingServer,
			TaskID: req.TaskId,
		})
		if err != nil {
			return errors.Annotate(err, "failed to collect task").Err()
		}
	case nil:
		return errors.Reason("missing Impl when isolating worker %s", w.Name).Err()
	default:
		return errors.Reason("Impl.Impl has unexpected type %T", wi).Err()
	}

	if result.State == common.Pending {
		if err = enqueueCollectRequest(c, req); err != nil {
			return err
		}
		return nil
	}

	// Worker state.
	workerState := tricium.State_SUCCESS
	if result.State == common.Failure {
		logging.Fields{
			"task ID":  req.TaskId,
			"build ID": req.BuildId,
		}.Infof(c, "Swarming task failed.")
		workerState = tricium.State_FAILURE
	}

	// Mark worker as done.
	b, err := proto.Marshal(&admin.WorkerDoneRequest{
		RunId:              req.RunId,
		Worker:             req.Worker,
		IsolatedOutputHash: result.IsolatedOutputHash,
		Provides:           w.Provides,
		State:              workerState,
		BuildbucketOutput:  result.BuildbucketOutput,
	})
	if err != nil {
		return errors.Annotate(err, "failed to encode worker done request").Err()
	}
	t := tq.NewPOSTTask("/tracker/internal/worker-done", nil)
	t.Payload = b
	if err := tq.Add(c, common.TrackerQueue, t); err != nil {
		return errors.Annotate(err, "failed to enqueue track request").Err()
	}

	// Abort here if worker failed and mark descendants as failures.
	if workerState == tricium.State_FAILURE {
		logging.Fields{
			"worker": req.Worker,
			"run ID": req.RunId,
		}.Warningf(c, "Execution of worker failed.")
		var tasks []*tq.Task
		for _, worker := range wf.GetWithDescendants(req.Worker) {
			if worker == req.Worker {
				continue
			}
			// Mark descendant worker as done and failed.
			b, err := proto.Marshal(&admin.WorkerDoneRequest{
				RunId:  req.RunId,
				Worker: worker,
				State:  tricium.State_ABORTED,
			})
			if err != nil {
				return errors.Annotate(err, "failed to encode worker done request").Err()
			}
			t := tq.NewPOSTTask("/tracker/internal/worker-done", nil)
			t.Payload = b
			tasks = append(tasks, t)
		}
		if err := tq.Add(c, common.TrackerQueue, tasks...); err != nil {
			return errors.Annotate(err, "failed to enqueue track request").Err()
		}
		return nil
	}

	// If we have isolated output, create layered isolated input, include the input
	// in the collect request and massage the isolated output into new isolated input.
	isolatedInput := req.IsolatedInputHash
	if result.IsolatedOutputHash != "" {
		isolatedInput, err = isolator.LayerIsolates(
			c, wf.IsolateServer, req.IsolatedInputHash, result.IsolatedOutputHash)
		if err != nil {
			return errors.Annotate(err, "failed layer isolates").Err()
		}
	}

	// Enqueue trigger requests for successors.
	for _, worker := range wf.GetNext(req.Worker) {
		b, err := proto.Marshal(&admin.TriggerRequest{
			RunId:             req.RunId,
			IsolatedInputHash: isolatedInput,
			Worker:            worker,
		})
		if err != nil {
			return errors.Annotate(err, "failed to marshal successor trigger request").Err()
		}
		t := tq.NewPOSTTask("/driver/internal/trigger", nil)
		t.Payload = b
		if err := tq.Add(c, common.DriverQueue, t); err != nil {
			return errors.Annotate(err, "failed to enqueue collect request").Err()
		}
	}
	return nil
}
