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
	http.HandleFunc("/workflow-launcher/queue-handler", queueHandler)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Get the Run entry from the key in the queue
	strID := r.FormValue("ID")
	key, err := common.GetRunKey(ctx, strID)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	run, err := common.GetRun(ctx, key)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// TODO(emso): Get merged config from luci-config and
	// compute workflow using metafile info provided in the task.

	// TODO(emso): Create change details from information provided in the task,
	// this data will be consumed by the first task of the workflow.

	// TODO(emso): Launch workflow via SwarmBucket providing the workflow config and
	// change details as build properties.

	// Register that this run is now launched
	run.RunState = common.LAUNCHED

	err = common.StoreRunUpdates(ctx, key, run)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Enqueue workflow listener task
	e := map[string][]string{
		"Name": {"Workflow Listener Task"},
		"ID":   {strID},
	}
	t := taskqueue.NewPOSTTask("/workflow-listener/queue-handler", e)
	if _, e := taskqueue.Add(ctx, t, "workflow-listener-queue"); e != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
