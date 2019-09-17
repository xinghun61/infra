// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/appengine"
)

func main() {
	r := router.New()

	// This does not require auth. Needed for index page.
	basemw := standard.Base()

	templatesmw := basemw.Extend(templates.WithTemplates(&templates.Bundle{
		Loader:  templates.FileSystemLoader("templates"),
		FuncMap: templateFuncs,
	}))

	standard.InstallHandlers(r)

	r.GET("/", templatesmw, index)

	r.GET("/_task/auditor", basemw.Extend(gaemiddleware.RequireTaskQueue("default")), Auditor)

	r.GET("/_cron/scheduler", basemw.Extend(gaemiddleware.RequireCron), Scheduler)

	r.GET("/admin/smoketest", basemw, SmokeTest)

	r.GET("/view/status", templatesmw, Status)

	http.DefaultServeMux.Handle("/", r)
	appengine.Main()
}

// Handler for the index page.
func index(rc *router.Context) {
	templates.MustRender(rc.Context, rc.Writer, "pages/index.html", templates.Args{})
}
