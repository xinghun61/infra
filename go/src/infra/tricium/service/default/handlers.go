// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the default module.
package handlers

import (
	"net/http"
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

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Create and add run entry
	id, err := common.NewRun(ctx)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Pass on to the workflow launcher
	e := map[string][]string{
		"Name": {"Workflow Launcher Task"},
		"ID":   {strconv.FormatInt(id, 10)},
	}
	t := taskqueue.NewPOSTTask("/workflow-launcher/queue-handler", e)
	if _, err := taskqueue.Add(ctx, t, "workflow-launcher-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
