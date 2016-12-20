// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package config implements HTTP handlers for the config module.
package config

import (
	"net/http"
)

func init() {
	http.HandleFunc("/projects", projectsHandler)
	http.HandleFunc("/generate", generateHandler)
	http.HandleFunc("/validate", validateHandler)
}

func projectsHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should provide project details for connected projects.
}

func generateHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should generate a workflow configuration.
}

func validateHandler(w http.ResponseWriter, r *http.Request) {
	// TODO(emso): Add handler code.
	// This handler should validate the provided Tricium config (project and/or service).
}
