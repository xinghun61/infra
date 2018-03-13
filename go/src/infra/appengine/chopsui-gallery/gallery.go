// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gallery

import (
	"net/http"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

var templateBundle = &templates.Bundle{
	Loader:    templates.FileSystemLoader("templates"),
	DebugMode: info.IsDevAppServer,
}

func pageBase() router.MiddlewareChain {
	return standard.Base().Extend(templates.WithTemplates(templateBundle))
}

func init() {
	r := router.New()
	basemw := pageBase()
	standard.InstallHandlers(r)

	rootRouter := router.New()
	rootRouter.GET("/*path", basemw, gallery)

	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/api/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/internal/", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}

func gallery(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	templates.MustRender(c, w, "pages/index.html", templates.Args{})
}
