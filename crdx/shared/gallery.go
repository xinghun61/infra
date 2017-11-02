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
	standard.InstallHandlers(r)
	r.GET("/", pageBase(), gallery)
	http.DefaultServeMux.Handle("/", r)
}

func gallery(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	templates.MustRender(c, w, "pages/docs.html", templates.Args{})
}
