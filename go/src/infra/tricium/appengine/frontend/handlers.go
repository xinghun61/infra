// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the default (frontend) module.
package frontend

import (
	"errors"
	"fmt"
	"html/template"
	"net/http"
	"time"

	"github.com/google/go-querystring/query"

	"golang.org/x/net/context"

	"google.golang.org/appengine"
	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

var baseTemplate = template.Must(template.ParseFiles("templates/base.html"))

// showBasePage executes the base page template.
// This is the service landing page showing navigation links, a form for
// Gerrit analysis requests, and a status message (provided as an argument).
func showBasePage(ctx context.Context, w http.ResponseWriter, m string) {
	u := map[string]interface{}{
		"StatusMsg": m,
	}
	if err := baseTemplate.Execute(w, u); err != nil {
		common.ReportServerError(ctx, w, err)
	}
}

func init() {
	http.HandleFunc("/internal/analyze", analyzeHandler)
	http.HandleFunc("/internal/queue", queueHandler)
	http.HandleFunc("/results", resultsPageHandler)
	http.HandleFunc("/", landingPageHandler)
}

func landingPageHandler(w http.ResponseWriter, r *http.Request) {
	showBasePage(appengine.NewContext(r), w, "This service is under construction.")
}

func resultsPageHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)
	// Read run state from datastore.
	q := datastore.NewQuery("Run").Order("-Received").Limit(20)
	var runs []track.Run
	_, err := q.GetAll(ctx, &runs)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	// Show results template.
	d := map[string]interface{}{
		"Runs": runs,
	}
	t := template.Must(template.ParseFiles("templates/results.html"))
	if err := t.Execute(w, d); err != nil {
		common.ReportServerError(ctx, w, err)
	}
}

func analyzeHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	r.ParseForm()
	log.Infof(ctx, "[frontend] Raw analyze request: %v", r.Form)

	// Verify form values.
	project := r.FormValue("Project")
	ref := r.FormValue("GitRef")
	path := []string{}
	for _, p := range r.Form["Path[]"] {
		path = append(path, p)
	}
	if project == "" || ref == "" || len(path) == 0 {
		common.ReportServerError(ctx, w, errors.New("missing required information"))
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
		common.ReportServerError(ctx, w, errors.New("failed to encode service request"))
		return
	}
	t := taskqueue.NewPOSTTask("/internal/queue", v)
	if _, err := taskqueue.Add(ctx, t, "service-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Return the landing page with a status message.
	showBasePage(appengine.NewContext(r), w, "Analysis request sent.")

	log.Infof(ctx, "[frontend] Analysis request enqueued")
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	r.ParseForm()

	// Parse service request.
	if err := r.ParseForm(); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	sr, err := pipeline.ParseServiceRequest(r.Form)
	if err != nil {
		common.ReportServerError(ctx, w, err)
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
		if _, err := taskqueue.Add(ctx, tl, "launcher-queue"); err != nil {
			return fmt.Errorf("faile to enqueue launch request: %v", err)
		}
		return nil
	}, nil)
	if err != nil {
		common.ReportServerError(ctx, w, fmt.Errorf("failed to track and launch request: %v", err))
		return
	}
}
