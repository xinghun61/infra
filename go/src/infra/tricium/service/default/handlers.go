// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the default module.
package handlers

import (
	"html/template"
	"net/http"

	"google.golang.org/appengine"
	"google.golang.org/appengine/taskqueue"
)

func init() {
	http.HandleFunc("/", landingPageHandler)
	http.HandleFunc("/analyze", analyzeHandler)
}

var basePage = template.Must(template.ParseFiles("templates/base.html"))

func landingPageHandler(w http.ResponseWriter, r *http.Request) {
	data := map[string]interface{}{
		"Msg":             "This service is under construction ...",
		"ShowRequestForm": true,
	}
	basePage.Execute(w, data)
}

func analyzeHandler(w http.ResponseWriter, r *http.Request) {
	ctx := appengine.NewContext(r)
	t := taskqueue.NewPOSTTask("/workflow-launcher/queue-handler", map[string][]string{"name": {"Analyze Request"}})
	if _, err := taskqueue.Add(ctx, t, "workflow-launcher-queue"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	data := map[string]interface{}{
		"Msg": "Dummy analysis request sent.",
	}
	basePage.Execute(w, data)
}
