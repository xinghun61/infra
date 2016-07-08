// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the gerrit-poller module.
package handlers

import (
	"html/template"
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"
)

func init() {
	http.HandleFunc("/gerrit-poller/status", statusPageHandler)
	http.HandleFunc("/gerrit-poller/poll", pollHandler)
}

var basePage = template.Must(template.ParseFiles("templates/base.html"))

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add Gerrit poller stats
	data := map[string]interface{}{
		"Msg": "Status of the Gerrit Poller ...",
	}
	basePage.Execute(w, data)
}

func pollHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Poll Gerrit and convert changes to workflow event tasks.

	// Enqueue workflow event task.
	t := taskqueue.NewPOSTTask("/workflow-launcher/queue-handler", map[string][]string{"name": {"Analysis Request"}})
	if _, err := taskqueue.Add(ctx, t, "workflow-launcher-queue"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}
