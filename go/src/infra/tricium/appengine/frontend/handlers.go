// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the frontend (default) module.
package frontend

import (
	"errors"
	"fmt"
	"net/http"

	"github.com/google/go-querystring/query"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

func landingPageHandler(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", map[string]interface{}{
		"StatusMsg": "This service is under construction.",
	})
}

func resultsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	if _, err := runs(c); err != nil {
		logging.WithError(err).Errorf(c, "Results handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	templates.MustRender(c, w, "pages/results.html", map[string]interface{}{
		"Runs": runs,
	})
}

func runs(c context.Context) ([]*track.Run, error) {
	var runs []*track.Run
	q := ds.NewQuery("Run").Order("-Received").Limit(20)
	if err := ds.GetAll(c, q, &runs); err != nil {
		logging.WithError(err).Errorf(c, "Failed to read run entries from datastore")
		return nil, err
	}
	return runs, nil
}

func analyzeHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	sr, err := parseRequestForm(r)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to parse analyze request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if _, err := analyze(c, sr); err != nil {
		logging.WithError(err).Errorf(c, "Analyze handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "Analyzer handler successfully completed")
	templates.MustRender(c, w, "pages/index.html", map[string]interface{}{
		"StatusMsg": "Analysis request sent.",
	})
}

func parseRequestForm(r *http.Request) (*pipeline.ServiceRequest, error) {
	r.ParseForm()
	project := r.FormValue("Project")
	ref := r.FormValue("GitRef")
	paths := []string{}
	for _, p := range r.Form["Path[]"] {
		paths = append(paths, p)
	}
	if project == "" || ref == "" || len(paths) == 0 {
		return nil, fmt.Errorf("Missing required information, project: %s, ref: %s, paths: %v", project, ref, paths)
	}
	return &pipeline.ServiceRequest{
		Project: project,
		GitRef:  ref,
		Path:    paths,
	}, nil
}

// TODO(emso): Replace this analyze function with a pRPC Analyze RPC.
func analyze(c context.Context, sr *pipeline.ServiceRequest) (int64, error) {
	// TODO(emso): Verify that the project in the request is known.
	// TODO(emso): Verify that the user making the request has permission.
	// TODO(emso): Verify that there is no current run for this request (map hashed requests to run IDs).
	// TODO(emso): Read Git repo info from the configuration projects/ endpoint.
	repo := "https://chromium-review.googlesource.com/playground/gerrit-tricium"
	run := &track.Run{
		Received: clock.Now(c).UTC(),
		State:    track.Pending,
	}
	err := ds.RunInTransaction(c, func(c context.Context) error {
		// Add tracking entries for run and request.
		if err := ds.Put(c, run); err != nil {
			return err
		}
		logging.Infof(c, "[frontend] Run ID: %s, key: %s", run.ID, ds.KeyForObj(c, run))
		req := &track.ServiceRequest{
			Parent:  ds.KeyForObj(c, run),
			Project: sr.Project,
			Path:    sr.Path,
			GitRepo: repo,
			GitRef:  sr.GitRef,
		}
		if err := ds.Put(c, req); err != nil {
			return err
		}
		// Launch workflow, enqueue launch request.
		rl := pipeline.LaunchRequest{
			RunID:   run.ID,
			Project: sr.Project,
			Path:    sr.Path,
			GitRepo: repo,
			GitRef:  sr.GitRef,
		}
		v, err := query.Values(rl)
		if err != nil {
			return errors.New("failed to encode launch request")
		}
		t := tq.NewPOSTTask("/launcher/internal/queue", v)
		return tq.Add(c, common.LauncherQueue, t)
	}, nil)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to track and launch request")
		return 0, err
	}
	return run.ID, nil
}

// queueHandler calls analyze for entries in the queue.
//
// This queue is intended as a service extension point for modules
// running within the Tricium GAE app. For instance, the Gerrit poller.
// TODO(emso): Figure out if this queue is needed.
// TODO(emso): Figure out if/where WrapTransient should be used for errors.
func queueHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	if err := r.ParseForm(); err != nil {
		logging.WithError(err).Errorf(c, "Failed to parse service request form")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	sr, err := pipeline.ParseServiceRequest(r.Form)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to parse service request")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "[frontend] Parsed service request (project: %s, Git ref: %s)", sr.Project, sr.GitRef)
	if _, err := analyze(c, sr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to handle analyze request")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}
