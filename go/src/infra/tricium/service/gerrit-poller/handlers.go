// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the gerrit-poller module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/gerrit-poller/status", statusPageHandler)
	http.HandleFunc("/gerrit-poller/poll", pollHandler)
}

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add Gerrit poller stats
	d := map[string]interface{}{
		"Msg": "Status of the Gerrit Poller ...",
	}
	common.ShowBasePage(appengine.NewContext(r), w, d)
}

func pollHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// TODO(emso): Poll Gerrit and convert changes to workflow event tasks.

	// Enqueue service task.
	e := map[string][]string{
		"Name": {"Gerrit Analysis Request"},
	}
	t := taskqueue.NewPOSTTask("/queue-handler", e)
	if _, err := taskqueue.Add(ctx, t, "service-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
