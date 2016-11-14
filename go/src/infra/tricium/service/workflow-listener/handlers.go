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
	http.HandleFunc("/workflow-listener/queue-handler", queueHandler)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Get the run key from the ID in the queue.
	strID := r.FormValue("ID")
	key, err := common.GetRunKey(ctx, strID)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Get the run entry from the key.
	// TODO(emso): Use the returned run entry.
	_, err = common.GetRun(ctx, key)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// TODO(emso): Process task (find LogDog streams to listen to) and listen to events.

	// Enqueue reporter task.
	e := map[string][]string{
		"Name": {"Reporter Event"},
		"ID":   {strID},
	}
	t := taskqueue.NewPOSTTask("/reporter/queue-handler", e)
	if _, err := taskqueue.Add(ctx, t, "reporter-queue"); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
