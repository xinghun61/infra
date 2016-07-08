// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers to the workflow-listener module.
package handlers

import (
	"html/template"
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"
)

func init() {
	http.HandleFunc("/workflow-listener/status", statusPageHandler)
	http.HandleFunc("/workflow-listener/queue-handler", queueHandler)
}

var basePage = template.Must(template.ParseFiles("templates/base.html"))

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add workflow listener stats
	data := map[string]interface{}{
		"Msg": "Status of the Workflow Listener ...",
	}
	basePage.Execute(w, data)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Process task (find LogDog streams to listen to) and listen to events.

	// Enqueue gerrit reporter task.
	t := taskqueue.NewPOSTTask("/gerrit-reporter/queue-handler", map[string][]string{"name": {"Workflow Event"}})
	if _, err := taskqueue.Add(ctx, t, "gerrit-reporter-queue"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}
