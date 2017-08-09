// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements the Tricium driver.
package driver

import (
	"net/http"

	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/server/router"

	"google.golang.org/appengine"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/driver/internal/trigger", base, triggerHandler)
	r.POST("/driver/internal/collect", base, collectHandler)

	// Devserver can't accept PubSub pushes, use manual PubSub pulls instead in development.
	if appengine.IsDevAppServer() {
		r.GET("/driver/internal/pull", base, pubsubPullHandler)
	} else {
		r.POST("/_ah/push-handlers/notify", base, pubsubPushHandler)
	}

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterDriverServer(s, server)
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
