// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package config implements the Tricium config module.
package config

import (
	"net/http"

	"go.chromium.org/luci/server/router"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterConfigServer(s, server)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	http.DefaultServeMux.Handle("/", r)
}
