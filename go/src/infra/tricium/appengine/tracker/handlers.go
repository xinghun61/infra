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

	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"

	"github.com/luci/luci-go/server/router"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/tracker/internal/queue", base, queueHandler)

	http.DefaultServeMux.Handle("/", r)
}

func queueHandler(c *router.Context) {
	ctx := common.NewGAEContext(c)

	// Parse track request.
	if err := c.Request.ParseForm(); err != nil {
		common.ReportServerError(c, err)
		return
	}
	rr, err := pipeline.ParseTrackRequest(c.Request.Form)
	if err != nil {
		common.ReportServerError(c, err)
		return
	}

	switch rr.Kind {
	case pipeline.TrackWorkflowLaunched:
		err = handleWorkflowLaunched(ctx, rr)
	case pipeline.TrackWorkerLaunched:
		err = handleWorkerLaunched(ctx, rr)
	case pipeline.TrackWorkerDone:
		err = handleWorkerDone(ctx, rr)
	default:
		err = fmt.Errorf("Unknown kind: %d", rr.Kind)
	}
	if err != nil {
		common.ReportServerError(c, fmt.Errorf("Failed to handle track request: %v", err))
	}
}

func handleWorkflowLaunched(ctx context.Context, rr *pipeline.TrackRequest) error {
	log.Infof(ctx, "[tracker] Workflow launched (run ID: %s)", rr.RunID)
	// Read workflow config from datastore and add tracking entries for analyzers and workers.
	workflowKey := datastore.NewKey(ctx, "Workflow", "", rr.RunID, nil)
	e := new(common.Entity)
	if err := datastore.Get(ctx, workflowKey, e); err != nil {
		return fmt.Errorf("Failed to retrieve workflow config: %v", err)
	}
	wf := &admin.Workflow{}
	if err := jsonpb.Unmarshal(bytes.NewReader(e.Value), wf); err != nil {
		return fmt.Errorf("Failed to unmarshal workflow config: %v", err)
	}
	log.Infof(ctx, "[tracker] Read workflow config: %# v", wf)
	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		// Update state of run to launched.
		run := &track.Run{}
		runKey := datastore.NewKey(ctx, "Run", "", rr.RunID, nil)
		if err := datastore.Get(ctx, runKey, run); err != nil {
			return fmt.Errorf("Failed to retrieve run: %v", err)
		}
		run.State = track.Launched
		if _, err := datastore.Put(ctx, runKey, run); err != nil {
			return fmt.Errorf("Failed to mark workflow as launched: %v", err)
		}
		if err := enableTrackingOfWorkflow(ctx, wf, runKey); err != nil {
			return fmt.Errorf("Failed to enable tracking of workflow: %v", err)
		}
		return nil
	}, nil)
}

func handleWorkerLaunched(ctx context.Context, rr *pipeline.TrackRequest) error {
	log.Infof(ctx, "[tracker] Worker launched (run ID: %s, worker: %s)", rr.RunID, rr.Worker)

	runKey := datastore.NewKey(ctx, "Run", "", rr.RunID, nil)
	// Assuming that the analyzer name is included in the worker name, before the first underscore.
	analyzerName := strings.Split(rr.Worker, "_")[0]
	analyzerKey := datastore.NewKey(ctx, "Analyzer", analyzerName, 0, runKey)
	workerKey := datastore.NewKey(ctx, "Worker", rr.Worker, 0, analyzerKey)
	log.Infof(ctx, "[tracker] Looking up worker, key: %s", workerKey)

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		done := make(chan error)
		// Update worker state, set to launched.
		go func() {
			worker := &track.Worker{}
			if err := datastore.Get(ctx, workerKey, worker); err != nil {
				done <- fmt.Errorf("Failed to retrieve worker: %v", err)
			}
			worker.State = track.Launched
			if _, err := datastore.Put(ctx, workerKey, worker); err != nil {
				done <- fmt.Errorf("Failed to mark worker as launched: %v", err)
			}
			done <- nil
		}()
		// Maybe update analyzer state, set to launched.
		analyzer := &track.AnalyzerRun{}
		if err := datastore.Get(ctx, analyzerKey, analyzer); err != nil {
			return fmt.Errorf("Failed to retrieve analyzer: %v", err)
		}
		if analyzer.State == track.Pending {
			analyzer.State = track.Launched
			if _, err := datastore.Put(ctx, analyzerKey, analyzer); err != nil {
				return fmt.Errorf("Failed to mark analyzer as launched: %v", err)
			}
		}
		// Wait for result from worker update.
		if err := <-done; err != nil {
			return err
		}
		return nil
	}, nil)
}

func handleWorkerDone(ctx context.Context, rr *pipeline.TrackRequest) error {
	log.Infof(ctx, "[tracker] Worker done (run ID: %s, worker: %s)", rr.RunID, rr.Worker)
	runKey := datastore.NewKey(ctx, "Run", "", rr.RunID, nil)
	// Assuming that the analyzer name is included in the worker name, before the first underscore.
	analyzerName := strings.Split(rr.Worker, "_")[0]
	analyzerKey := datastore.NewKey(ctx, "AnalyzerRun", analyzerName, 0, runKey)
	workerKey := datastore.NewKey(ctx, "Worker", rr.Worker, 0, analyzerKey)
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		// Update worker state, set to done-*.
		worker := &track.Worker{}
		if err := datastore.Get(ctx, workerKey, worker); err != nil {
			return fmt.Errorf("Failed to retrieve worker: %v", err)
		}
		// TODO(emso): add DoneFailure if results
		if rr.ExitCode != 0 {
			worker.State = track.DoneException
		} else {
			worker.State = track.DoneSuccess
		}
		// TODO(emso): add result details from isolated output.
		if _, err := datastore.Put(ctx, workerKey, worker); err != nil {
			return fmt.Errorf("Failed to mark worker as done-*: %v", err)
		}
		return nil
	}, nil)
	if err != nil {
		return err
	}
	return propagateStateUpdate(ctx, runKey, analyzerKey)
}

func propagateStateUpdate(ctx context.Context, runKey, analyzerKey *datastore.Key) error {
	// Fetch workers of analyzer.
	workers := []*track.Worker{}
	q := datastore.NewQuery("Worker").Ancestor(analyzerKey)
	t := q.Run(ctx)
	for {
		w := &track.Worker{}
		_, err := t.Next(w)
		if err == datastore.Done {
			break
		}
		if err != nil {
			return fmt.Errorf("Failed to retrieve worker: %v", err)
		}
		workers = append(workers, w)
	}
	// Update analyzer state, set to done-* if all workers are done.
	analyzer := &track.AnalyzerRun{}
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, analyzerKey, analyzer); err != nil {
			return fmt.Errorf("Failed to retrieve analyzer: %v", err)
		}
		// Assume analyzer success and then review state of workers.
		prevState := analyzer.State
		analyzer.State = track.DoneSuccess
		for _, aw := range workers {
			// When all workers are done, aggregate the result.
			// All worker DoneSuccess -> analyzer DoneSuccess
			// One or more workers DoneFailure -> analyzer DoneFailure
			// If not DoneFailure, then one or more workers DoneException -> analyzer DoneException
			if aw.State == track.DoneSuccess || aw.State == track.DoneFailure || aw.State == track.DoneException {
				if aw.State == track.DoneFailure {
					analyzer.State = track.DoneFailure
				} else if aw.State == track.DoneException && analyzer.State == track.DoneSuccess {
					analyzer.State = track.DoneException
				}
			} else {
				// Found non-done worker, no change to be made - abort.
				return nil
			}
		}
		// If state change for analyzer, store updated analyzer state.
		if prevState != analyzer.State {
			if _, err := datastore.Put(ctx, analyzerKey, analyzer); err != nil {
				return fmt.Errorf("Failed to mark analyzer as done-*: %v", err)
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
	analyzers := []*track.AnalyzerRun{}
	q = datastore.NewQuery("AnalyzerRun").Ancestor(runKey)
	t = q.Run(ctx)
	for {
		a := &track.AnalyzerRun{}
		_, err := t.Next(a)
		if err == datastore.Done {
			break
		}
		if err != nil {
			return fmt.Errorf("Failed to retrieve analyzer: %v", err)
		}
		analyzers = append(analyzers, a)
	}

	// Maybe uupdate run state.
	err = datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		run := &track.Run{}
		if err := datastore.Get(ctx, runKey, run); err != nil {
			return fmt.Errorf("Failed to retrieve run: %v", err)
		}
		// Store previous run state and assume success.
		prevState := run.State
		run.State = track.DoneSuccess
		for _, a := range analyzers {
			// When all analyzers are done, aggregate the result.
			// All analyzers DoneSuccess -> run DoneSuccess
			// One or more analyzers DoneFailure -> run DoneFailure
			// If not DoneFailure, then one or more analyzers DoneException -> run DoneException
			if a.State == track.DoneSuccess || a.State == track.DoneFailure || a.State == track.DoneException {
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
			if _, err := datastore.Put(ctx, runKey, run); err != nil {
				return fmt.Errorf("Failed to mark run as done-*: %v", err)
			}
		}
		return nil
	}, nil)
	if err != nil {
		return err
	}
	return nil
}

type analyzerWorker struct {
	Analyzer *track.AnalyzerRun
	Worker   []*track.Worker
}

func enableTrackingOfWorkflow(ctx context.Context, wf *admin.Workflow, runKey *datastore.Key) error {
	// Extract analyzer-*worker structure from workflow config.
	am := map[string]*analyzerWorker{}
	for _, w := range wf.Workers {
		analyzer := strings.Split(w.Name, "_")[0]
		a, ok := am[analyzer]
		if !ok {
			a = &analyzerWorker{
				Analyzer: &track.AnalyzerRun{
					Name: analyzer,
				},
			}
			am[analyzer] = a
		}
		aw := &track.Worker{
			Name:     w.Name,
			State:    track.Pending,
			Platform: w.Platform,
		}
		for _, n := range w.Next {
			aw.Next = append(aw.Next, n)
		}
		a.Worker = append(a.Worker, aw)
		log.Infof(ctx, "Found analyzer/worker: %v", a)
	}
	log.Infof(ctx, "[tracker] Extracted analyzers and workers from config: %# v", am)
	analyzerKeys := []*datastore.Key{}
	analyzerValues := []*track.AnalyzerRun{}
	workerKeys := []*datastore.Key{}
	workerValues := []*track.Worker{}
	// Store tracking entries.
	for k, v := range am {
		analyzerKey := datastore.NewKey(ctx, "Analyzer", k, 0, runKey)
		log.Infof(ctx, "[tracker] Storing analyzer entry (key: %s, analyzer: %v)", analyzerKey, v.Analyzer)
		analyzerKeys = append(analyzerKeys, analyzerKey)
		analyzerValues = append(analyzerValues, v.Analyzer)
		for _, tw := range v.Worker {
			workerKey := datastore.NewKey(ctx, "Worker", tw.Name, 0, analyzerKey)
			log.Infof(ctx, "[tracker] Storing worker entry (key: %s, worker: %v)", workerKey, tw.Name)
			workerKeys = append(workerKeys, workerKey)
			workerValues = append(workerValues, tw)
		}
	}
	if _, err := datastore.PutMulti(ctx, analyzerKeys, analyzerValues); err != nil {
		return fmt.Errorf("Failed to store analyzer entries: %v", err)
	}
	if _, err := datastore.PutMulti(ctx, workerKeys, workerValues); err != nil {
		return fmt.Errorf("Failed to store worker entries: %v", err)
	}
	return nil
}
