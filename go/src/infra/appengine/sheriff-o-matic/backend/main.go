// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements HTTP server that handles requests to the backend analyzer module.
package main

import (
	"net/http"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/handler"

	"google.golang.org/appengine"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

const (
	prodAppID = "sheriff-o-matic"
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
	return standard.Base().Extend(a.GetMiddleware()).Extend(withServiceClients)
}

func withServiceClients(ctx *router.Context, next router.Handler) {
	a := analyzer.New(5, 100)
	setServiceClients(ctx, a)
	ctx.Context = handler.WithAnalyzer(ctx.Context, a)
	next(ctx)
}

func setServiceClients(ctx *router.Context, a *analyzer.Analyzer) {
	if info.AppID(ctx.Context) == prodAppID {
		findIt, crBug, _, testResults := client.ProdClients(ctx.Context)
		a.CrBug = crBug
		a.FindIt = findIt
		a.TestResults = testResults
	} else {
		findIt, crBug, _, testResults := client.StagingClients(ctx.Context)
		a.CrBug = crBug
		a.FindIt = findIt
		a.TestResults = testResults
	}
}

//// Routes.
func init() {
	r := router.New()
	basemw := base()
	standard.InstallHandlers(r)

	r.GET("/_cron/analyze/:tree", basemw, handler.GetAnalyzeHandler)
	r.GET("/_ah/queue/addannotationtrees", basemw, handler.AnnotationTreeWorker)

	http.DefaultServeMux.Handle("/", r)
}

func main() {
	appengine.Main()
}
