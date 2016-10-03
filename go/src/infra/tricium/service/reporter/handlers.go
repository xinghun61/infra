// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the reporter module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/datastore"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/results", resultsPageHandler)
	http.HandleFunc("/reporter/queue-handler", queueHandler)
}

func resultsPageHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Read run state from datastore
	q := datastore.NewQuery("Run").Order("-Received").Limit(20)
	var runs []common.Run
	_, err := q.GetAll(ctx, &runs)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
	common.ShowResultsPage(appengine.NewContext(r), w, runs)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)

	// Get the key for the string repsentation of the run id.
	strID := r.FormValue("ID")
	key, err := common.GetRunKey(ctx, strID)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// Get the run entry.
	run, err := common.GetRun(ctx, key)
	if err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// TODO(emso): Also read progress and results from the queue.
	// TODO(emso): Process request (put progress/results in data store).

	// Register that this run is now done.
	run.RunState = common.DONE

	if err := common.StoreRunUpdates(ctx, key, run); err != nil {
		common.ReportServerError(ctx, w, err)
		return
	}

	// TODO(emso): Check which reporter to re-route to, for now, enqueue a Gerrit reporter task.

	// Enqueue Gerrit reporter task
	e := map[string][]string{
		"Name": {"Gerrit Reporter Task"},
		"ID":   {strID},
	}
	t := taskqueue.NewPOSTTask("/gerrit-reporter/queue-handler", e)
	if _, e := taskqueue.Add(ctx, t, "gerrit-reporter-queue"); e != nil {
		common.ReportServerError(ctx, w, err)
		return
	}
}
