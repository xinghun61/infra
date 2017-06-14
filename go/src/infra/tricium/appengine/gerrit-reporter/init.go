// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerritreporter implements the Tricium Gerrit reporter.
package gerritreporter

import (
	"net/http"

	"github.com/luci/luci-go/grpc/discovery"
	"github.com/luci/luci-go/server/router"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/gerrit-reporter/internal/launched", base, launchedHandler)
	r.POST("/gerrit-reporter/internal/completed", base, completedHandler)
	r.POST("/gerrit-reporter/internal/results", base, resultsHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterReporterServer(s, server)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
