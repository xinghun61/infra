// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the reporter module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/results", resultsPageHandler)
	http.HandleFunc("/reporter/queue-handler", queueHandler)
}

func resultsPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Show results and progress of current workflows
	d := map[string]interface{}{
		"Msg": "Results and progress workflows ...",
	}
	common.ShowBasePage(w, d)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Process request (put progress/results in data store)

	// TODO(emso): Check which reporter to reroute to, for now, enqueue a Gerrit reporter task
	t := taskqueue.NewPOSTTask("/gerrit-reporter/queue-handler", map[string][]string{"name": {"Gerrit Reporter Event"}})
	if _, e := taskqueue.Add(ctx, t, "gerrit-reporter-queue"); e != nil {
		http.Error(w, e.Error(), http.StatusInternalServerError)
		return
	}
}
