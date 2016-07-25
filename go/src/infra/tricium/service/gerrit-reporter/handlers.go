// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the gerrit-reporter module.
package handlers

import (
	"net/http"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/gerrit-reporter/status", statusPageHandler)
	http.HandleFunc("/gerrit-reporter/queue-handler", queueHandler)
}

func statusPageHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add Gerrit reporter stats
	d := map[string]interface{}{
		"Msg": "Status of the Gerrit Reporter ...",
	}
	common.ShowBasePage(w, d)
}

func queueHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Process request and report event to Gerrit
}
