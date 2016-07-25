// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the default module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/", landingPageHandler)
	http.HandleFunc("/analyze", analyzeHandler)
}

func landingPageHandler(w http.ResponseWriter, r *http.Request) {
	d := map[string]interface{}{
		"Msg":             "This service is under construction ...",
		"ShowRequestForm": true,
	}
	common.ShowBasePage(w, d)
}

func analyzeHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)
	t := taskqueue.NewPOSTTask("/workflow-launcher/queue-handler", map[string][]string{"name": {"Analyze Request"}})
	if _, err := taskqueue.Add(ctx, t, "workflow-launcher-queue"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	d := map[string]interface{}{
		"Msg": "Dummy analysis request sent.",
	}
	common.ShowBasePage(w, d)
}
