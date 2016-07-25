// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the workflow-launcher module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/workflow-launcher/status", statusPageHandler)
	http.HandleFunc("/workflow-launcher/queue-handler", queueHandler)
}

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add workflow launcher stats
	d := map[string]interface{}{
		"Msg": "Status of the Workflow Launcher ...",
	}
	common.ShowBasePage(w, d)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Process request (merge configs, compute workflow) and launch workflow

	// Enqueue workflow listener task
	t := taskqueue.NewPOSTTask("/workflow-listener/queue-handler", map[string][]string{"name": {"Workflow Launched"}})
	if _, e := taskqueue.Add(ctx, t, "workflow-listener-queue"); e != nil {
		http.Error(w, e.Error(), http.StatusInternalServerError)
		return
	}
}
