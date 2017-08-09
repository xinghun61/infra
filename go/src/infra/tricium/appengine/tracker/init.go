// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tracker implements the Tricium tracker.
package tracker

import (
	"net/http"

	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/server/router"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/tracker/internal/worker-done", base, workerDoneHandler)
	r.POST("/tracker/internal/worker-launched", base, workerLaunchedHandler)
	r.POST("/tracker/internal/workflow-launched", base, workflowLaunchedHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterTrackerServer(s, server)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
