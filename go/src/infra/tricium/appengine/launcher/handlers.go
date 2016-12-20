// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package launcher implements HTTP handlers for the launcher module.
package launcher

import (
	"errors"
	"fmt"
	"net/http"

	"github.com/golang/protobuf/jsonpb"
	"github.com/google/go-querystring/query"

	"google.golang.org/appengine"
	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/taskqueue"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
)

func init() {
	http.HandleFunc("/launcher/internal/queue", queueHandler)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Parse launch request.
	if err := r.ParseForm(); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	lr, err := pipeline.ParseLaunchRequest(r.Form)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	log.Infof(ctx, "[launcher] Launch request (run ID: %d)", lr.RunID)

	// Store workflow as 'Workflow' entity, using run ID as key.
	// TODO(emso): Get workflow config from config module.
	wf := admin.Workflow{
		WorkerTopic:    "projects/tricium-dev/topics/worker-completion",
		ServiceAccount: "emso@chromium.org",
		Workers: []*admin.Worker{
			{
				Name:     "Hello_Ubuntu14.04_x86-64",
				Needs:    tricium.Data_GIT_FILE_DETAILS,
				Provides: tricium.Data_FILES,
				Platform: "Ubuntu14.04_x86-64",
				Dimensions: []string{
					"pool:Chrome",
					"os:Ubuntu-14.04",
					"cpu:x84-64",
				},
				Cmd: &tricium.Cmd{
					Exec: "echo",
					Args: []string{
						"'hello'",
					},
				},
				Deadline: 30,
			},
		},
	}
	m := jsonpb.Marshaler{}
	wfs, err := m.MarshalToString(&wf)
	if err != nil {
		common.ReportServerError(ctx, w, fmt.Errorf("Failed to marshal workflow: %v", err))
		return
	}
	workflowKey := datastore.NewKey(ctx, "Workflow", "", lr.RunID, nil)
	e := new(common.Entity)
	e.Value = []byte(wfs)
	if _, err := datastore.Put(ctx, workflowKey, e); err != nil {
		common.ReportServerError(ctx, w, fmt.Errorf("Failed to store workflow: %v", err))
		return
	}

	// TODO(emso): Create initial Tricium data, git file details.
	// TODO(emso): Isolate created Tricium data.
	isolatedInput := "abcdef"

	// TODO(emso): Get root workers from the workflow config.
	workers := []string{"Hello_Ubuntu14.04_x86-64"}

	// Track progress, enqueue track request.
	rr := pipeline.TrackRequest{
		Kind:  pipeline.TrackWorkflowLaunched,
		RunID: lr.RunID,
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

	// Trigger root workers, enqueue driver requests.
	for _, worker := range workers {
		rd := pipeline.DriverRequest{}
		rd.Kind = pipeline.DriverTrigger
		rd.RunID = lr.RunID
		rd.IsolatedInput = isolatedInput
		rd.Worker = worker
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

}
