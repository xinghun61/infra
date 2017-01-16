// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements functionalityfor the frontend (default) module.
package frontend

import (
	"net/http"

	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/grpc/discovery"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/server/router"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForUI()

	// LUCI frameworks needs a bunch of routes exposed via default module.
	gaemiddleware.InstallHandlers(r, base)

	// TODO(emso): Should these use MiddlewareForInternal? Are they called by
	// end-users?
	r.POST("/internal/analyze-form", base, analyzeFormHandler)
	r.POST("/internal/analyze", base, analyzeHandler)

	r.GET("/results", base, resultsHandler)
	r.GET("/", base, landingPageHandler)

	// Configure pRPC server.
	// TODO(emso): Enable authentication
	s := prpc.Server{Authenticator: prpc.NoAuthenticator}
	tricium.RegisterTriciumServer(&s, server)
	discovery.Enable(&s)
	s.InstallHandlers(r, base)

	http.DefaultServeMux.Handle("/", r)
}
