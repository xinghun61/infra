// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the default (frontend) module.
package frontend

import (
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/google/go-querystring/query"

	"golang.org/x/net/context"

	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/taskqueue"

	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

func init() {
	r := router.New()
	base := common.MiddlewareForUI()

	// LUCI frameworks needs a bunch of routes exposed via default module.
	gaemiddleware.InstallHandlers(r, base)

	// TODO(emso): Should these use MiddlewareForInternal? Are they called by
	// end-users?
	r.POST("/internal/analyze", base, analyzeHandler)
	r.POST("/internal/queue", base, queueHandler)

	r.GET("/results", base, resultsPageHandler)
	r.GET("/", base, landingPageHandler)

	http.DefaultServeMux.Handle("/", r)
}

func landingPageHandler(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", map[string]interface{}{
		"StatusMsg": "This service is under construction.",
	})
}

func resultsPageHandler(c *router.Context) {
	ctx := common.NewGAEContext(c)
	// Read run state from datastore.
	q := datastore.NewQuery("Run").Order("-Received").Limit(20)
	var runs []track.Run
	_, err := q.GetAll(ctx, &runs)
	if err != nil {
		common.ReportServerError(c, err)
		return
	}
	// Show results template.
	templates.MustRender(c.Context, c.Writer, "pages/results.html", map[string]interface{}{
		"Runs": runs,
	})
}

func analyzeHandler(c *router.Context) {
	ctx := common.NewGAEContext(c)

	c.Request.ParseForm()
	log.Infof(ctx, "[frontend] Raw analyze request: %v", c.Request.Form)

	// Verify form values.
	project := c.Request.FormValue("Project")
	ref := c.Request.FormValue("GitRef")
	path := []string{}
	for _, p := range c.Request.Form["Path[]"] {
		path = append(path, p)
	}
	if project == "" || ref == "" || len(path) == 0 {
		common.ReportServerError(c, errors.New("missing required information"))
		return
	}

	// Add to the service queue.
	sr := pipeline.ServiceRequest{
		Project: project,
		GitRef:  ref,
		Path:    path,
	}
	v, err := query.Values(sr)
	if err != nil {
		common.ReportServerError(c, errors.New("failed to encode service request"))
		return
	}
	t := taskqueue.NewPOSTTask("/internal/queue", v)
	if _, err := taskqueue.Add(ctx, t, common.ServiceQueue); err != nil {
		common.ReportServerError(c, err)
		return
	}

	// Return the landing page with a status message.
	templates.MustRender(c.Context, c.Writer, "pages/index.html", map[string]interface{}{
		"StatusMsg": "Analysis request sent.",
	})

	log.Infof(ctx, "[frontend] Analysis request enqueued")
}

func queueHandler(c *router.Context) {
	ctx := common.NewGAEContext(c)

	c.Request.ParseForm()

	// Parse service request.
	if err := c.Request.ParseForm(); err != nil {
		common.ReportServerError(c, err)
		return
	}
	sr, err := pipeline.ParseServiceRequest(c.Request.Form)
	if err != nil {
		common.ReportServerError(c, err)
		return
	}

	log.Infof(ctx, "[frontend] Parsed service request (project: %s, Git ref: %s)", sr.Project, sr.GitRef)

	// TODO(emso): Verify that the project in the request is known.
	// TODO(emso): Verify that the user making the request has permission.
	// TODO(emso): Verify that there is no current run for this request (map hashed requests to run IDs).

	// TODO(emso): Read Git repo info from the configuration projects/ endpoint.
	repo := "https://chromium-review.googlesource.com/playground/gerrit-tricium"

	err = datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		// Create run entry.
		run := &track.Run{
			Received: time.Now(),
			State:    track.Pending,
		}
		req := &track.ServiceRequest{
			Project: sr.Project,
			Path:    sr.Path,
			GitRepo: repo,
			GitRef:  sr.GitRef,
		}
		k := datastore.NewIncompleteKey(ctx, "Run", nil)
		runKey, err := datastore.Put(ctx, k, run)
		if err != nil {
			return fmt.Errorf("failed to add run entry: %v", err)
		}
		reqKey := datastore.NewKey(ctx, "ServiceRequest", "", 0, runKey)
		if _, err = datastore.Put(ctx, reqKey, req); err != nil {
			return fmt.Errorf("failed to add service request entry: %v", err)
		}
		// Launch workflow, enqueue launch request.
		rl := pipeline.LaunchRequest{
			RunID:   runKey.IntID(),
			Project: sr.Project,
			Path:    sr.Path,
			GitRepo: repo,
			GitRef:  sr.GitRef,
		}
		vl, err := query.Values(rl)
		if err != nil {
			return errors.New("failed to encode launch request")
		}
		tl := taskqueue.NewPOSTTask("/launcher/internal/queue", vl)
		if _, err := taskqueue.Add(ctx, tl, common.LauncherQueue); err != nil {
			return fmt.Errorf("faile to enqueue launch request: %v", err)
		}
		return nil
	}, nil)
	if err != nil {
		common.ReportServerError(c, fmt.Errorf("failed to track and launch request: %v", err))
		return
	}
}
