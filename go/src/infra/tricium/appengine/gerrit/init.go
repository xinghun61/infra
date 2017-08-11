// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerrit implements the Tricium Gerrit integration.
package gerrit

import (
	"net/http"

	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/server/router"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.GET("/gerrit/internal/poll", base, pollHandler)

	r.POST("/gerrit/internal/report-launched", base, launchedHandler)
	r.POST("/gerrit/internal/report-completed", base, completedHandler)
	r.POST("/gerrit/internal/report-results", base, resultsHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterReporterServer(s, reporter)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
