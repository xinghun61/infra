// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements the Tricium driver.
package driver

import (
	"net/http"

	"github.com/luci/luci-go/server/router"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/driver/internal/trigger", base, triggerHandler)
	r.POST("/driver/internal/collect", base, collectHandler)
	r.POST("/_ah/push-handlers/notify", base, notifyHandler)

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterDriverServer(s, server)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
