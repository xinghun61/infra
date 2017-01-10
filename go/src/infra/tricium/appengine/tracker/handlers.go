// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tracker implements HTTP handlers for the tracker module.
package tracker

import (
	"bytes"
	"fmt"
	"net/http"
	"strings"

	"github.com/golang/protobuf/jsonpb"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

// TODO(emso): Extract to the shared common package.
type workflowConfigProvider interface {
	readConfig(context.Context, int64) (*admin.Workflow, error)
}

func queueHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	if err := r.ParseForm(); err != nil {
		logging.WithError(err).Errorf(c, "tracker queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	rr, err := pipeline.ParseTrackRequest(r.Form)
	if err != nil {
		logging.WithError(err).Errorf(c, "tracker queue handler encountered errors")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[tracker] Track request (run ID: %d, kind: %d)", rr.RunID, rr.Kind)
	switch rr.Kind {
	case pipeline.TrackWorkflowLaunched:
		err = handleWorkflowLaunched(c, rr, &datastoreConfigProvider{})
	case pipeline.TrackWorkerLaunched:
		err = handleWorkerLaunched(c, rr)
	case pipeline.TrackWorkerDone:
		err = handleWorkerDone(c, rr)
	default:
		logging.Errorf(c, "unknown kind: %d", rr.Kind)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if err != nil {
		logging.WithError(err).Errorf(c, "tracker queue handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "[tracker] Successfully completed")
	w.WriteHeader(http.StatusOK)
}

// handleWorkflowLaunched reads the workflow configuration for the run ID in the track request,
// marks the run as launched, and adds tracking entries for analyzers and workers in the workflow
// of the run.
func handleWorkflowLaunched(c context.Context, rr *pipeline.TrackRequest, wp workflowConfigProvider) error {
	logging.Infof(c, "[tracker] Workflow launched (run ID: %s)", rr.RunID)
	wf, err := wp.readConfig(c, rr.RunID)
	if err != nil {
		return fmt.Errorf("failed to read workflow config: %v", err)
	}
	return ds.RunInTransaction(c, func(c context.Context) error {
		run := &track.Run{ID: rr.RunID}
		if err := ds.Get(c, run); err != nil {
			return fmt.Errorf("failed to retrieve run entry: %v", err)
		}
		run.State = track.Launched
		if err := ds.Put(c, run); err != nil {
			return fmt.Errorf("failed to mark workflow as launched: %v", err)
		}
		if err := enableTrackingOfWorkers(c, wf, run); err != nil {
			return fmt.Errorf("failed to enable tracking of workers: %v", err)
		}
		return nil
	}, nil)
}

func handleWorkerLaunched(c context.Context, rr *pipeline.TrackRequest) error {
	logging.Infof(c, "[tracker] Worker launched (run ID: %s, worker: %s)", rr.RunID, rr.Worker)
	_, analyzerKey, workerKey := createKeys(c, rr.RunID, rr.Worker)
	logging.Infof(c, "[tracker] Looking up worker, key: %s", workerKey)
	return ds.RunInTransaction(c, func(c context.Context) (err error) {
		done := make(chan error)
		defer func() {
			if err2 := <-done; err == nil {
				err = err2
			}
		}()
		// Update worker state, set to launched.
		go func() {
			w := &track.WorkerInvocation{
				ID:     workerKey.StringID(),
				Parent: workerKey.Parent(),
			}
			if err := ds.Get(c, w); err != nil {
				done <- fmt.Errorf("failed to retrieve worker: %v", err)
				return
			}
			w.State = track.Launched
			if err := ds.Put(c, w); err != nil {
				done <- fmt.Errorf("failed to mark worker as launched: %v", err)
				return
			}
			done <- nil
		}()
		// Maybe update analyzer state, set to launched.
		a := &track.AnalyzerInvocation{
			ID:     analyzerKey.StringID(),
			Parent: analyzerKey.Parent(),
		}
		if err := ds.Get(c, a); err != nil {
			return fmt.Errorf("failed to retrieve analyzer: %v", err)
		}
		if a.State == track.Pending {
			a.State = track.Launched
			if err := ds.Put(c, a); err != nil {
				return fmt.Errorf("failed to mark analyzer as launched: %v", err)
			}
		}
		return nil
	}, nil)
}

func handleWorkerDone(c context.Context, rr *pipeline.TrackRequest) error {
	logging.Infof(c, "[tracker] Worker done (run ID: %s, worker: %s)", rr.RunID, rr.Worker)
	runKey, analyzerKey, workerKey := createKeys(c, rr.RunID, rr.Worker)
	err := ds.RunInTransaction(c, func(c context.Context) error {
		// Update worker state, set to done-*.
		w := &track.WorkerInvocation{
			ID:     workerKey.StringID(),
			Parent: workerKey.Parent(),
		}
		if err := ds.Get(c, w); err != nil {
			return fmt.Errorf("failed to retrieve worker: %v", err)
		}
		// TODO(emso): add DoneFailure if results
		if rr.ExitCode != 0 {
			w.State = track.DoneException
		} else {
			w.State = track.DoneSuccess
		}
		// TODO(emso): add result details from isolated output.
		if err := ds.Put(c, w); err != nil {
			return fmt.Errorf("failed to mark worker as done-*: %v", err)
		}
		return nil
	}, nil)
	if err != nil {
		return err
	}
	return propagateStateUpdate(c, runKey, analyzerKey)
}

func createKeys(c context.Context, runID int64, worker string) (*ds.Key, *ds.Key, *ds.Key) {
	runKey := ds.NewKey(c, "Run", "", runID, nil)
	// Assuming that the analyzer name is included in the worker name, before the first underscore.
	analyzerName := strings.Split(worker, "_")[0]
	analyzerKey := ds.NewKey(c, "AnalyzerInvocation", analyzerName, 0, runKey)
	return runKey, analyzerKey, ds.NewKey(c, "WorkerInvocation", worker, 0, analyzerKey)
}

func propagateStateUpdate(c context.Context, runKey, analyzerKey *ds.Key) error {
	// Fetch workers of analyzer.
	var workers []*track.WorkerInvocation
	if err := ds.GetAll(c, ds.NewQuery("WorkerInvocation").Ancestor(analyzerKey), &workers); err != nil {
		return fmt.Errorf("failed to retrieve worker invocations: %v", err)
	}
	// Update analyzer state, set to done-* if all workers are done.
	analyzer := &track.AnalyzerInvocation{
		ID:     analyzerKey.StringID(),
		Parent: analyzerKey.Parent(),
	}
	err := ds.RunInTransaction(c, func(c context.Context) error {
		if err := ds.Get(c, analyzer); err != nil {
			return fmt.Errorf("failed to retrieve analyzer: %v", err)
		}
		// Assume analyzer success and then review state of workers.
		prevState := analyzer.State
		analyzer.State = track.DoneSuccess
		for _, w := range workers {
			// When all workers are done, aggregate the result.
			// All worker DoneSuccess -> analyzer DoneSuccess
			// One or more workers DoneFailure -> analyzer DoneFailure
			// If not DoneFailure, then one or more workers DoneException -> analyzer DoneException
			if w.State.IsDone() {
				if w.State == track.DoneFailure {
					analyzer.State = track.DoneFailure
				} else if w.State == track.DoneException && analyzer.State == track.DoneSuccess {
					analyzer.State = track.DoneException
				}
			} else {
				// Found non-done worker, no change to be made - abort.
				return nil
			}
		}
		// If state change for analyzer, store updated analyzer state.
		if prevState != analyzer.State {
			if err := ds.Put(c, analyzer); err != nil {
				return fmt.Errorf("failed to mark analyzer as done-*: %v", err)
			}
		}
		return nil
	}, nil)
	if err != nil {
		return err
	}

	// If the analyzer is still launched mode, then we have nothing to propagate. Stop here.
	if analyzer.State == track.Launched {
		return nil
	}

	// Fetch analyzers of run.
	var analyzers []*track.AnalyzerInvocation
	if err := ds.GetAll(c, ds.NewQuery("AnalyzerInvocation").Ancestor(runKey), &analyzers); err != nil {
		return fmt.Errorf("failed to retrieve analyzer invocations: %v", err)
	}

	// Maybe update run state.
	err = ds.RunInTransaction(c, func(c context.Context) error {
		run := &track.Run{ID: runKey.IntID()}
		if err := ds.Get(c, run); err != nil {
			return fmt.Errorf("failed to retrieve run: %v", err)
		}
		// Store previous run state and assume success.
		prevState := run.State
		run.State = track.DoneSuccess
		for _, a := range analyzers {
			// When all analyzers are done, aggregate the result.
			// All analyzers DoneSuccess -> run DoneSuccess
			// One or more analyzers DoneFailure -> run DoneFailure
			// If not DoneFailure, then one or more analyzers DoneException -> run DoneException
			if a.State.IsDone() {
				if a.State == track.DoneFailure {
					run.State = track.DoneFailure
				} else if a.State == track.DoneException && run.State == track.DoneSuccess {
					run.State = track.DoneException
				}
			} else {
				// Found non-done analyzer, nothing to update - abort.
				return nil
			}
		}
		if prevState != run.State {
			// Update run state.
			if err := ds.Put(c, runKey, run); err != nil {
				return fmt.Errorf("failed to mark run as done-*: %v", err)
			}
		}
		return nil
	}, nil)
	if err != nil {
		return err
	}
	return nil
}

// enableTrackingOfWorkers adds tracking entries for analyzer and worker invocations to
// enable tracking of progress and results.
func enableTrackingOfWorkers(c context.Context, wf *admin.Workflow, run *track.Run) error {
	aw := extractAnalyzerWorkerStructure(c, wf)
	logging.Infof(c, "[tracker] Extracted analyzers and workers from config: %# v", aw)
	// Store analyzer invocation entries.
	entities := make([]interface{}, 0, len(aw))
	for _, v := range aw {
		logging.Infof(c, "[tracker] Analyzer entry (run ID: %s, analyzer: %v)", run.ID, v.Analyzer)
		v.Analyzer.Parent = ds.KeyForObj(c, run)
		entities = append(entities, v.Analyzer)
	}
	// Store worker invocation entries.
	for _, v := range aw {
		for _, vv := range v.Workers {
			logging.Infof(c, "[tracker] Worker entry (run ID: %s, worker: %v)", run.ID, vv.Name)
			vv.Parent = ds.KeyForObj(c, v.Analyzer)
			entities = append(entities, vv)
		}
	}
	if err := ds.Put(c, entities); err != nil {
		return fmt.Errorf("failed to store analyzer and worker entries: %v", err)
	}
	return nil
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
			Platform: w.Platform,
		}
		for _, n := range w.Next {
			aw.Next = append(aw.Next, n)
		}
		a.Workers = append(a.Workers, aw)
		logging.Infof(c, "Found analyzer/worker: %v", a)
	}
	return m
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
