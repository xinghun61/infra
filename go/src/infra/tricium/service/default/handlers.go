// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the default module.
package handlers

import (
	"fmt"
	"net/http"
	"net/url"
	"strconv"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/", landingPageHandler)
	http.HandleFunc("/analyze", analyzeHandler)
	http.HandleFunc("/queue-handler", queueHandler)
}

func landingPageHandler(w http.ResponseWriter, r *http.Request) {
	common.ShowBasePage(appengine.NewContext(r), w, "This service is under construction.")
}

func analyzeHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Verify form values.
	cctx := r.FormValue("Context")
	curl := r.FormValue("ChangeURL")
	cinst := r.FormValue("Instance")
	cproj := r.FormValue("Project")
	cid := r.FormValue("ChangeID")
	crev := r.FormValue("Revision")
	cref := r.FormValue("GitRef")
	if cctx == "" || curl == "" || cinst == "" || cproj == "" || cid == "" || crev == "" || cref == "" {
		common.ReportServerError(ctx, w, fmt.Errorf("missing required information"))
		return
	}

	// Add to the service queue.
	u := url.Values{}
	u.Add("Context", cctx)
	u.Add("ChangeURL", curl)
	u.Add("Instance", cinst)
	u.Add("Project", cproj)
	u.Add("ChangeID", cid)
	u.Add("Revision", crev)
	u.Add("GitRef", cref)
	t := taskqueue.NewPOSTTask("/queue-handler", u)
	if _, err := taskqueue.Add(ctx, t, "service-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Return the landing page with a status message.
	common.ShowBasePage(appengine.NewContext(r), w, "Analysis request sent.")
}

// TODO(emso): Add authentication checks.
func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Dedup service tasks.
	// That is, check for already active runs for changes in the queue.
	// If there is a run entry for a change that is not DONE then
	// consider the task a dup and drop (with logging).

	// Create and add run entry.
	ictx, err := strconv.Atoi(r.FormValue("Context"))
	if err != nil {
		common.ReportServerError(ctx, w, fmt.Errorf("Context parameter: %s", err))
		return
	}
	cctx := common.ChangeContext(ictx)
	curl := r.FormValue("ChangeURL")
	id, err := common.NewRun(ctx, cctx, curl)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	u := url.Values{}
	u.Add("ID", strconv.FormatInt(id, 10))
	u.Add("Context", strconv.Itoa(ictx))
	u.Add("ChangeURL", curl)
	// TODO(emso): Add filtering for other contexts
	u.Add("Instance", r.FormValue("Instance"))
	u.Add("Project", r.FormValue("Project"))
	u.Add("ChangeID", r.FormValue("ChangeID"))
	u.Add("Revision", r.FormValue("Revision"))
	u.Add("GitRef", r.FormValue("GitRef"))
	t := taskqueue.NewPOSTTask("/workflow-launcher/queue-handler", u)
	if _, err := taskqueue.Add(ctx, t, "workflow-launcher-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
