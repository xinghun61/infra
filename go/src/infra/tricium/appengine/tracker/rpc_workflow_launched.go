// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"fmt"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
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
	if err := workflowLaunched(c, req, config.WorkflowCache); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to track workflow launched: %v", err)
	}
	return &admin.WorkflowLaunchedResponse{}, nil
}

func workflowLaunched(c context.Context, req *admin.WorkflowLaunchedRequest, wp config.WorkflowCacheAPI) error {
	wf, err := wp.GetWorkflow(c, req.RunId)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	// Prepare analyzer and worker invocation tracking entries to store.
	aw := extractAnalyzerWorkerStructure(c, wf)
	logging.Debugf(c, "Extracted analyzer/worker entries for tracking: %#v", aw)
	requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
	if err := ds.RunInTransaction(c, func(c context.Context) (err error) {
		// Store the root of the workflow.
		run := &track.WorkflowRun{
			ID:                1,
			Parent:            requestKey,
			IsolateServerURL:  wf.IsolateServer,
			SwarmingServerURL: wf.SwarmingServer,
		}
		if err := ds.Put(c, run); err != nil {
			return fmt.Errorf("failed to store WorkflowRun entity (run ID: %d): %v", run.ID, err)
		}
		runKey := ds.KeyForObj(c, run)
		ops := []func() error{
			// Update AnalyzeRequestResult to RUNNING.
			func() error {
				r := &track.AnalyzeRequestResult{
					ID:     1,
					Parent: requestKey,
					State:  tricium.State_RUNNING,
				}
				if err := ds.Put(c, r); err != nil {
					return fmt.Errorf("failed to mark request as launched: %v", err)
				}
				return nil
			},
			// Update WorkflowRun state to RUNNING.
			func() error {
				r := &track.WorkflowRunResult{
					ID:     1,
					Parent: runKey,
					State:  tricium.State_RUNNING,
				}
				if err := ds.Put(c, r); err != nil {
					return fmt.Errorf("failed to mark workflow as launched: %v", err)
				}
				return nil
			},
			// Store analyzer and worker run entities for tracking.
			func() error {
				entities := make([]interface{}, 0, len(aw))
				for _, v := range aw {
					v.Analyzer.Parent = runKey
					analyzerKey := ds.KeyForObj(c, v.Analyzer)
					entities = append(entities, []interface{}{
						v.Analyzer,
						&track.AnalyzerRunResult{
							ID:     1,
							Parent: analyzerKey,
							Name:   v.Analyzer.ID,
							State:  tricium.State_PENDING,
						},
					}...)
					for _, worker := range v.Workers {
						worker.Parent = analyzerKey
						entities = append(entities, worker)
						workerKey := ds.KeyForObj(c, worker)
						entities = append(entities, []interface{}{
							worker,
							&track.WorkerRunResult{
								ID:     1,
								Name:   worker.ID,
								Parent: workerKey,
								State:  tricium.State_PENDING,
							},
						}...)
					}
				}
				if err := ds.Put(c, entities); err != nil {
					return fmt.Errorf("failed to store analyzer and worker entities: %v", err)
				}
				return nil
			},
		}
		return common.RunInParallel(ops)
	}, nil); err != nil {
		return err
	}
	// Notify reporter.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return fmt.Errorf("failed to get AnalyzeRequest entity (run ID: %d): %v", req.RunId, err)
	}
	switch request.Consumer {
	case tricium.Consumer_GERRIT:
		b, err := proto.Marshal(&admin.ReportLaunchedRequest{RunId: req.RunId})
		if err != nil {
			return fmt.Errorf("failed to encode report launched request: %v", err)
		}
		t := tq.NewPOSTTask("/gerrit/internal/report-launched", nil)
		t.Payload = b
		return tq.Add(c, common.GerritReporterQueue, t)
	default:
		// Do nothing.
	}
	return nil
}

type analyzerToWorkers struct {
	Analyzer *track.AnalyzerRun
	Workers  []*track.WorkerRun
}

// extractAnalyzerWorkerStructure extracts analyzer-*worker structure from workflow config.
func extractAnalyzerWorkerStructure(c context.Context, wf *admin.Workflow) map[string]*analyzerToWorkers {
	m := map[string]*analyzerToWorkers{}
	for _, w := range wf.Workers {
		analyzer, err := track.ExtractAnalyzerName(w.Name)
		if err != nil {
			logging.Errorf(c, "Failed to extract analyzer name: %v", err)
		}
		a, ok := m[analyzer]
		if !ok {
			a = &analyzerToWorkers{Analyzer: &track.AnalyzerRun{ID: analyzer}}
			m[analyzer] = a
		}
		aw := &track.WorkerRun{ID: w.Name, Platform: w.ProvidesForPlatform}
		for _, n := range w.Next {
			aw.Next = append(aw.Next, n)
		}
		a.Workers = append(a.Workers, aw)
		a.Analyzer.Workers = append(a.Analyzer.Workers, w.Name)
		logging.Debugf(c, "Found analyzer/worker: %v", a)
	}
	return m
}
