// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements functionalityfor the frontend (default) module.
package frontend

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/server/router"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForUI()
	baseInternal := common.MiddlewareForInternal()

	// LUCI frameworks needs a bunch of routes exposed via default module.
	standard.InstallHandlers(r)

	// This is the URL called from the analyze form, expose to end-users.
	// TODO(emso): Should this be internal?
	// NB! With polymer this goes a way and we call Tricium.Analyze directly.
	r.POST("/internal/analyze-form", base, analyzeFormHandler)

	// This is the analyze queue handler
	r.POST("/internal/analyze", baseInternal, analyzeHandler)

	r.GET("/results", base, resultsHandler)
	r.GET("/", base, landingPageHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	tricium.RegisterTriciumServer(s, server)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
