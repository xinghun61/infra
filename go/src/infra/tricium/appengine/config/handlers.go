// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package config implements HTTP handlers for the config module.
package config

import (
	"net/http"

	"github.com/luci/luci-go/server/router"

	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	// TODO(emso): Switch to MiddlewareForREST if endpoints below are API-like.
	base := common.MiddlewareForUI()

	r.GET("/projects", base, projectsHandler)
	r.GET("/generate", base, generateHandler)
	r.GET("/validate", base, validateHandler)

	http.DefaultServeMux.Handle("/", r)
}

func projectsHandler(c *router.Context) {
	// TODO(emso): Add handler code.
	// This handler should provide project details for connected projects.
}

func generateHandler(c *router.Context) {
	// TODO(emso): Add handler code.
	// This handler should generate a workflow configuration.
}

func validateHandler(c *router.Context) {
	// TODO(emso): Add handler code.
	// This handler should validate the provided Tricium config (project and/or service).
}
