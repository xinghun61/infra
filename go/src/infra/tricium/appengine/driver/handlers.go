// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements HTTP handlers to the driver module.
package driver

import (
	"bytes"
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/jsonpb"
	"github.com/google/go-querystring/query"
	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
)

type workflowConfigProvider interface {
	readConfig(context.Context, int64) (*admin.Workflow, error)
}

func queueHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	if err := r.ParseForm(); err != nil {
		logging.WithError(err).Errorf(c, "Driver queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	dr, err := pipeline.ParseDriverRequest(r.Form)
	if err != nil {
		logging.WithError(err).Errorf(c, "Driver queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Driver request (run ID: %d, Worker: %s)", dr.RunID, dr.Worker)
	if err = drive(c, dr, &datastoreConfigProvider{}); err != nil {
		logging.WithError(err).Errorf(c, "Driver queue handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "[driver] Successfully completed")
	w.WriteHeader(http.StatusOK)
}

func drive(c context.Context, dr *pipeline.DriverRequest, wp workflowConfigProvider) error {
	switch dr.Kind {
	case pipeline.DriverTrigger:
		return handleTrigger(c, dr, wp)
	case pipeline.DriverCollect:
		return handleCollect(c, dr, wp)
	default:
		return fmt.Errorf("Unknown driver request kind: %d", dr.Kind)
	}
}

func handleTrigger(c context.Context, dr *pipeline.DriverRequest, wp workflowConfigProvider) error {
	logging.Infof(c, "[driver]: Received trigger request (run ID: %d, worker: %s)", dr.RunID, dr.Worker)
	_, err := wp.readConfig(c, dr.RunID)
	if err != nil {
		return fmt.Errorf("Failed to read workflow config: %v", err)
	}
	// TODO(emso): Auth check.
	// TODO(emso): Runtime type check.
	// TODO(emso): Isolate swarming input.
	// TODO(emso): Launch swarming task and get actual task URL. Put
	// runID, worker name, and hash tp isolated input in pubsub userdata.
	swarmingURL := "https://chromium-swarm-dev.appspot.com"
	taskID := "123456789"
	// Report progress, enqueue reporter request, marking worker as launched.
	rr := pipeline.TrackRequest{
		Kind:          pipeline.TrackWorkerLaunched,
		RunID:         dr.RunID,
		Worker:        dr.Worker,
		IsolatedInput: dr.IsolatedInput,
		SwarmingURL:   swarmingURL,
		TaskID:        taskID,
	}
	vr, err := query.Values(rr)
	if err != nil {
		return fmt.Errorf("Failed to encode track request: %v", err)
	}
	tr := tq.NewPOSTTask("/tracker/internal/queue", vr)
	if err := tq.Add(c, common.TrackerQueue, tr); err != nil {
		return fmt.Errorf("Failed to enqueue track request: %v", err)
	}
	return nil
}

func handleCollect(c context.Context, dr *pipeline.DriverRequest, wp workflowConfigProvider) error {
	logging.Infof(c, "[driver]: Received collect request (run ID: %d, worker: %s)", dr.RunID, dr.Worker)
	wf, err := wp.readConfig(c, dr.RunID)
	if err != nil {
		return fmt.Errorf("Failed to read workflow config: %v", err)
	}
	// TODO(emso): Collect results from swarming task, getting actual isolated output and exit code.
	isolatedOutput := "abcdefg"
	exitCode := 0
	// Report progress, enqueue reporter request, marking worker as launched.
	rr := pipeline.TrackRequest{
		Kind:           pipeline.TrackWorkerDone,
		RunID:          dr.RunID,
		Worker:         dr.Worker,
		IsolatedOutput: isolatedOutput,
		ExitCode:       exitCode,
	}
	vr, err := query.Values(rr)
	if err != nil {
		return fmt.Errorf("Failed to encode track request: %v", err)
	}
	tr := tq.NewPOSTTask("/tracker/internal/queue", vr)
	if err := tq.Add(c, common.TrackerQueue, tr); err != nil {
		return fmt.Errorf("Failed to enqueue track request: %v", err)
	}
	// TODO(emso): Massage actual isolated output to isolated input for successors.
	isolatedInput := "abcdefg"
	// Trigger root workers, enqueue driver requests.
	for _, worker := range successorWorkers(dr.Worker, wf) {
		rd := pipeline.DriverRequest{
			Kind:          pipeline.DriverTrigger,
			RunID:         dr.RunID,
			IsolatedInput: isolatedInput,
			Worker:        worker,
		}
		vd, err := query.Values(rd)
		if err != nil {
			return fmt.Errorf("Failed to encode driver request: %v", err)
		}
		td := tq.NewPOSTTask("/driver/internal/queue", vd)
		if err := tq.Add(c, common.DriverQueue, td); err != nil {
			return fmt.Errorf("Failed to enqueue driver request: %v", err)
		}
	}
	return nil
}

func notifyHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	logging.Infof(c, "[driver]: Received notify")
	// TODO(emso): Extract actual run ID, isolated input hash, and worker name from notification details.
	runID := 1234567
	isolatedInput := "abcdefg"
	worker := "Hello_Ubuntu14.04_x86-64"

	rd := pipeline.DriverRequest{
		Kind:          pipeline.DriverCollect,
		RunID:         int64(runID),
		IsolatedInput: isolatedInput,
		Worker:        worker,
	}
	vd, err := query.Values(rd)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to encode driver request: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	td := tq.NewPOSTTask("/driver/internal/queue", vd)
	if err := tq.Add(c, common.DriverQueue, td); err != nil {
		logging.WithError(err).Errorf(c, "Failed to enqueue driver request: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
}

type datastoreConfigProvider struct {
}

func (*datastoreConfigProvider) readConfig(c context.Context, runID int64) (*admin.Workflow, error) {
	e := &common.Entity{
		ID:   runID,
		Kind: "Workflow",
	}
	if err := ds.Get(c, e); err != nil {
		return nil, err
	}
	wf := &admin.Workflow{}
	if err := jsonpb.Unmarshal(bytes.NewBuffer(e.Value), wf); err != nil {
		return nil, err
	}
	return wf, nil
}

func successorWorkers(cw string, wf *admin.Workflow) []string {
	for _, w := range wf.Workers {
		if w.Name == cw {
			return w.Next
		}
	}
	return nil
}
