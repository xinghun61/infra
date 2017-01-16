// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements the Tricium driver.
package driver

import (
	"net/http"

	"github.com/luci/luci-go/grpc/discovery"
	"github.com/luci/luci-go/grpc/prpc"
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
	// TODO(emso): Enable authentication
	s := prpc.Server{Authenticator: prpc.NoAuthenticator}
	admin.RegisterDriverServer(&s, server)
	discovery.Enable(&s)
	s.InstallHandlers(r, base)

	http.DefaultServeMux.Handle("/", r)
}
