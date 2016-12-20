// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements HTTP handlers to the driver module.
package driver

import (
	"errors"
	"fmt"
	"net/http"

	"github.com/google/go-querystring/query"

	"google.golang.org/appengine"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
)

func init() {
	http.HandleFunc("/driver/internal/queue", queueHandler)
	http.HandleFunc("/_ah/push-handlers/notify", notifyHandler)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Parse driver request.
	if err := r.ParseForm(); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	dr, err := pipeline.ParseDriverRequest(r.Form)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	switch dr.Kind {
	case pipeline.DriverTrigger:
		log.Infof(ctx, "[driver]: Received trigger request (runID: %d, worker: %s)", dr.RunID, dr.Worker)

		// TODO(emso): Read workflow config.
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
			common.ReportServerError(ctx, w, errors.New("failed to encode reporter request"))
			return
		}
		tr := taskqueue.NewPOSTTask("/tracker/internal/queue", vr)
		if _, err := taskqueue.Add(ctx, tr, "tracker-queue"); err != nil {
			common.ReportServerError(ctx, w, err)
			return
		}
	case pipeline.DriverCollect:
		log.Infof(ctx, "[driver]: Received collect request (runID: %d, worker: %s)", dr.RunID, dr.Worker)

		// TODO(emso): Read workflow config.
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
			common.ReportServerError(ctx, w, errors.New("failed to encode reporter request"))
			return
		}
		tr := taskqueue.NewPOSTTask("/tracker/internal/queue", vr)
		if _, err := taskqueue.Add(ctx, tr, "tracker-queue"); err != nil {
			common.ReportServerError(ctx, w, err)
			return
		}

		// TODO(emso): Get actual successors for this worker from the workflow config.
		successors := []string{}
		// TODO(emso): Massage actual isolated output to isolated input for successors.
		isolatedInput := "abcdefg"

		// Trigger root workers, enqueue driver requests.
		for _, worker := range successors {
			rd := pipeline.DriverRequest{
				Kind:          pipeline.DriverTrigger,
				RunID:         dr.RunID,
				IsolatedInput: isolatedInput,
				Worker:        worker,
			}
			vd, err := query.Values(rd)
			if err != nil {
				common.ReportServerError(ctx, w, errors.New("failed to encode launch request"))
				return
			}
			td := taskqueue.NewPOSTTask("/driver/internal/queue", vd)
			if _, err := taskqueue.Add(ctx, td, "driver-queue"); err != nil {
				common.ReportServerError(ctx, w, err)
				return
			}
		}
	default:
		common.ReportServerError(ctx, w, fmt.Errorf("Unknown kind: %s", dr.Kind))
	}
}

func notifyHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	log.Infof(ctx, "[driver]: Received notify")

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
		common.ReportServerError(ctx, w, errors.New("failed to encode driver request"))
		return
	}
	td := taskqueue.NewPOSTTask("/driver/internal/queue", vd)
	if _, err := taskqueue.Add(ctx, td, "driver-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
