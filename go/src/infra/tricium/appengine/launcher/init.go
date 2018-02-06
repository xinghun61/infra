// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package launcher implements HTTP handlers for the launcher module.
//
// The job of the workflow launcher is to bootstrap the execution of a workflow
// for an analysis request. This includes adding entries to the driver queue
// for the root workers of the workflow.
package launcher

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

	r.POST("/launcher/internal/launch", base, launchHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterLauncherServer(s, server)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
