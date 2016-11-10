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
	d := map[string]interface{}{
		"Msg":             "This service is under construction ...",
		"ShowRequestForm": true,
	}
	common.ShowBasePage(appengine.NewContext(r), w, d)
}

func analyzeHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO: Use common.AnalysisTask
	// Add to the service queue.
	e := map[string][]string{
		"Name": {"Service Task"},
	}
	t := taskqueue.NewPOSTTask("/queue-handler", e)
	if _, err := taskqueue.Add(ctx, t, "service-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Show request added page.
	d := map[string]interface{}{
		"Msg": "Dummy analysis request sent.",
	}
	common.ShowBasePage(appengine.NewContext(r), w, d)
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
