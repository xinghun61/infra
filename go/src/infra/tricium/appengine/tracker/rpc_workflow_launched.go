// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"fmt"
	"strings"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// TrackerServer represents the Tricium pRPC Tracker server.
type trackerServer struct{}

var server = &trackerServer{}

// WorkflowLaunched tracks the launch of a workflow.
func (*trackerServer) WorkflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest) (*admin.WorkflowLaunchedResponse, error) {
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := workflowLaunched(c, req, config.DatastoreWorkflowProvider); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track workflow launched: %v", err)
	}
	return &admin.WorkflowLaunchedResponse{}, nil
}

func workflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest, wp config.WorkflowProvider) error {
	wf, err := wp.ReadWorkflowForRun(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	// Prepare analyzer and worker invocation tracking entries to store.
	aw := extractAnalyzerWorkerStructure(c, wf)
	logging.Infof(c, "Extracted analyzer/worker entries for tracking: %#v", aw)
	return ds.RunInTransaction(c, func(c context.Context) (err error) {
		run := &track.Run{ID: req.RunId}
		if err := ds.Get(c, run); err != nil {
			return fmt.Errorf("failed to retrieve run entry (run ID: %d): %v", run.ID, err)
		}
		// Run the below operations in parallel.
		done := make(chan error)
		defer func() {
			if err2 := <-done; err2 != nil {
				err = err2
			}
		}()
		go func() {
			// Update Run state to launched.
			run.State = track.Launched
			if err := ds.Put(c, run); err != nil {
				done <- fmt.Errorf("failed to mark workflow as launched: %v", err)
			}
			done <- nil
		}()
		// Store analyzer and worker invocation entries for tracking.
		entities := make([]interface{}, 0, len(aw))
		for _, v := range aw {
			v.Analyzer.Parent = ds.KeyForObj(c, run)
			entities = append(entities, v.Analyzer)
		}
		for _, v := range aw {
			for _, vv := range v.Workers {
				vv.Parent = ds.KeyForObj(c, v.Analyzer)
				entities = append(entities, vv)
			}
		}
		if err := ds.Put(c, entities); err != nil {
			return fmt.Errorf("failed to store analyzer and worker entries: %v", err)
		}
		return nil
	}, nil)
}

type analyzerToWorkers struct {
	Analyzer *track.AnalyzerInvocation
	Workers  []*track.WorkerInvocation
}

// extractAnalyzerWorkerStructure extracts analyzer-*worker structure from workflow config.
func extractAnalyzerWorkerStructure(c context.Context, wf *admin.Workflow) map[string]*analyzerToWorkers {
	m := map[string]*analyzerToWorkers{}
	for _, w := range wf.Workers {
		analyzer := strings.Split(w.Name, "_")[0]
		a, ok := m[analyzer]
		if !ok {
			a = &analyzerToWorkers{
				Analyzer: &track.AnalyzerInvocation{
					ID:    analyzer,
					Name:  analyzer,
					State: track.Pending,
				},
			}
			m[analyzer] = a
		}
		aw := &track.WorkerInvocation{
			ID:       w.Name,
			Name:     w.Name,
			State:    track.Pending,
			Platform: w.ProvidesForPlatform.String(),
		}
		for _, n := range w.Next {
			aw.Next = append(aw.Next, n)
		}
		a.Workers = append(a.Workers, aw)
		logging.Infof(c, "Found analyzer/worker: %v", a)
	}
	return m
}
