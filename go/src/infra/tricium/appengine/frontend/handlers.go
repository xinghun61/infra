// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the frontend (default) module.
package frontend

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/tricium/api/v1"
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
		logging.WithError(err).Errorf(c, "results handler encountered errors")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	r, err := runs(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to retrieve runs")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	templates.MustRender(c, w, "pages/results.html", map[string]interface{}{
		"Runs": r,
	})
}

func runs(c context.Context) ([]*track.Run, error) {
	var runs []*track.Run
	q := ds.NewQuery("Run").Order("-Received").Limit(20)
	if err := ds.GetAll(c, q, &runs); err != nil {
		logging.WithError(err).Errorf(c, "failed to read run entries from datastore")
		return nil, err
	}
	return runs, nil
}

func analyzeHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	// TODO(emso): With a switch to Polymer this handler can be replaced with a direct
	// call to the pRPC server via Javascript fetch.
	sr, err := parseRequestForm(r)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to parse analyze request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	res, err := triciumServer.Analyze(c, &tricium.TriciumRequest{
		Project: sr.Project,
		GitRef:  sr.GitRef,
		Paths:   sr.Paths,
	})
	// TODO(emso): Sort out the returned error code to distinguish retriable errors
	// from fatal errors. For instance, grpc.Code(err) equal to codes.InvalidArgument is fatal, while
	// codes.Internal is not.
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to call Tricium.Analyze RPC")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "Analyzer handler successfully completed, run ID: %s", res.RunId)
	templates.MustRender(c, w, "pages/index.html", map[string]interface{}{
		"StatusMsg": fmt.Sprintf("Analysis request sent. Run ID: %s", res.RunId),
	})
	w.WriteHeader(http.StatusOK)
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
		Paths:   paths,
	}, nil
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
	// TODO(emso): Consider proto-serializing pRPC requests in the task payload for queues wrapping pRPC calls.
	_, err = triciumServer.Analyze(c, &tricium.TriciumRequest{
		Project: sr.Project,
		GitRef:  sr.GitRef,
		Paths:   sr.Paths,
	})
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to call Tricium.Analyze RPC")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}
