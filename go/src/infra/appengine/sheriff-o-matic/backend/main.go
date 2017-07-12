// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to the backend analyzer module.
package som

import (
	"net/http"

	"infra/appengine/sheriff-o-matic/som"

	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
)

// base is the root of the middleware chain.
func base() router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
			server.CookieAuth,
		},
	}
	return gaemiddleware.BaseProd().Extend(a.GetMiddleware())
}

//// Routes.
func init() {
	r := router.New()
	basemw := base()
	gaemiddleware.InstallHandlers(r)
	r.POST("/_ah/queue/changetestexpectations", basemw, som.LayoutTestExpectationChangeWorker)
	r.GET("/_cron/analyze/:tree", basemw, som.GetAnalyzeHandler)
	r.POST("/_ah/queue/logdiff", basemw, som.LogdiffWorker)

	http.DefaultServeMux.Handle("/", r)
}
