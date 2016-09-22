// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers to the workflow-listener module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/workflow-listener/status", statusPageHandler)
	http.HandleFunc("/workflow-listener/queue-handler", queueHandler)
}

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add workflow listener stats
	d := map[string]interface{}{
		"Msg": "Status of the Workflow Listener ...",
	}
	common.ShowBasePage(w, d)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Process task (find LogDog streams to listen to) and listen to events.

	// Enqueue reporter task.
	t := taskqueue.NewPOSTTask("/reporter/queue-handler", map[string][]string{"name": {"Workflow Event"}})
	if _, e := taskqueue.Add(ctx, t, "reporter-queue"); e != nil {
		http.Error(w, e.Error(), http.StatusInternalServerError)
		return
	}
}
