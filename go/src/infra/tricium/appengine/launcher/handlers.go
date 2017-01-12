// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package launcher implements HTTP handlers for the launcher module.
package launcher

import (
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
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
)

type workflowProvider interface {
	readConfig(context.Context, string) (*admin.Workflow, error)
}

type luciConfigProvider struct {
}

func queueHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	// TODO(emso): Convert to use serialized json strings (from json encoded structs)?
	if err := r.ParseForm(); err != nil {
		logging.WithError(err).Errorf(c, "Launch queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	lr, err := pipeline.ParseLaunchRequest(r.Form)
	if err != nil {
		logging.WithError(err).Errorf(c, "Launch queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[launcher] Launch request (run ID: %d)", lr.RunID)
	if err := launch(c, lr, &luciConfigProvider{}); err != nil {
		logging.WithError(err).Errorf(c, "Launch queue handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "[launcher] Successfully completed")
	w.WriteHeader(http.StatusOK)
}

func launch(c context.Context, lr *pipeline.LaunchRequest, wp workflowProvider) error {
	// Read and convert workflow to string.
	wf, err := wp.readConfig(c, lr.Project)
	if err != nil {
		return err
	}
	m := jsonpb.Marshaler{}
	wfs, err := m.MarshalToString(wf)
	if err != nil {
		return fmt.Errorf("Failed to marshal workflow: %v", err)
	}
	err = ds.RunInTransaction(c, func(c context.Context) error {
		// TODO(emso): Refactor code to use a type actually called Workflow and use standard binary proto encoding.
		// Store the workflow config, as kind 'Workflow' entity using run ID as key.
		e := &common.Entity{
			ID:    lr.RunID,
			Kind:  "Workflow",
			Value: []byte(wfs),
		}
		// TODO(emso): This call overrides any existing config for this run. If this is a retry there may already
		// be a config for this run, and this config may be different if there was a config change between retries.
		// Let the first config take precedence? Additional checking is needed to make sure workers are only
		// started once to avoid duplication in the pipeline.
		if err := ds.Put(c, e); err != nil {
			return fmt.Errorf("Failed to store workflow: %v", err)
		}
		// Track workflow as launched, the tracker needs the stored workflow config
		// to process this request.
		vr, err := query.Values(&pipeline.TrackRequest{
			Kind:  pipeline.TrackWorkflowLaunched,
			RunID: lr.RunID,
		})
		if err != nil {
			return fmt.Errorf("Failed to encode reporter request: %v", err)
		}
		tr := tq.NewPOSTTask("/tracker/internal/queue", vr)
		if err := tq.Add(c, common.TrackerQueue, tr); err != nil {
			return fmt.Errorf("Failed to enqueue reporter request: %v", err)
		}
		return nil
	}, nil)
	if err != nil {
		return fmt.Errorf("Failed to store workflow and track launch: %v", err)
	}
	// Isolate initial intput.
	inputHash, err := isolateGitFileDetails(lr.Project, lr.GitRepo, lr.GitRef, lr.Paths)
	if err != nil {
		return fmt.Errorf("Failed to isolate git file details: %v", err)
	}
	// Trigger root workers, enqueue driver requests.
	tasks := []*tq.Task{}
	for _, worker := range rootWorkers(wf) {
		vd, err := query.Values(&pipeline.DriverRequest{
			Kind:          pipeline.DriverTrigger,
			RunID:         lr.RunID,
			IsolatedInput: inputHash,
			Worker:        worker,
		})
		if err != nil {
			return fmt.Errorf("Failed to encode launch request: %v", err)
		}
		tasks = append(tasks, tq.NewPOSTTask("/driver/internal/queue", vd))
	}
	if err := tq.Add(c, common.DriverQueue, tasks...); err != nil {
		return fmt.Errorf("Failed to enqueue driver request: %v", err)
	}
	return nil
}

// rootWorkers returns the list of root workers from the workflow config.
//
// Root workers are those workers in need of the initial Tricium
// data type, i.e., Git file details.
func rootWorkers(wf *admin.Workflow) []string {
	var wl []string
	for _, w := range wf.Workers {
		if w.Needs == tricium.Data_GIT_FILE_DETAILS {
			wl = append(wl, w.Name)
		}
	}
	return wl
}

func isolateGitFileDetails(project, gitRepo, gitRef string, paths []string) (string, error) {
	// TODO(emso): Create initial Tricium data, git file details.
	// TODO(emso): Isolate created Tricium data.
	return "abcedfg", nil
}

func (s *luciConfigProvider) readConfig(c context.Context, project string) (*admin.Workflow, error) {
	// TODO(emso): Replace this dummy config with one read from luci-config.
	return &admin.Workflow{
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
	}, nil
}
