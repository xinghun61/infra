// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the workflow-launcher module.
package handlers

import (
	"html/template"
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"
)

func init() {
	http.HandleFunc("/workflow-launcher/status", statusPageHandler)
	http.HandleFunc("/workflow-launcher/queue-handler", queueHandler)
}

var basePage = template.Must(template.ParseFiles("templates/base.html"))

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add workflow launcher stats
	data := map[string]interface{}{
		"Msg": "Status of the Workflow Launcher ...",
	}
	basePage.Execute(w, data)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Process request (merge configs, compute workflow) and launch workflow

	// Enqueue workflow listener task
	t := taskqueue.NewPOSTTask("/workflow-listener/queue-handler", map[string][]string{"name": {"Workflow Launched"}})
	if _, err := taskqueue.Add(ctx, t, "workflow-listener-queue"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}
