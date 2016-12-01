// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the config module.
package handlers

import (
	"net/http"

	"google.golang.org/appengine"

	"infra/tricium/service/common"
)

func init() {
	http.HandleFunc("/projects", projectsHandler)
	http.HandleFunc("/generate", generateHandler)
	http.HandleFunc("/validate", validateHandler)
}

func projectsHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should provide project details for connected projects.
	common.ShowBasePage(appengine.NewContext(r), w, "Status of projects ...")
}

func generateHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should generate a workflow configuration.
	common.ShowBasePage(appengine.NewContext(r), w, "Status of generator ...")
}

func validateHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should validate the provided Tricium config (project and/or service).
	common.ShowBasePage(appengine.NewContext(r), w, "Status of validation ...")
}
