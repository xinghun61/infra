// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func init() {
	r := router.New()

	// This does not require auth. Needed for index page.
	basemw := standard.Base()

	templatesmw := basemw.Extend(templates.WithTemplates(&templates.Bundle{
		Loader:  templates.FileSystemLoader("templates"),
		FuncMap: templateFuncs,
	}))

	standard.InstallHandlers(r)

	r.GET("/", templatesmw, index)

	r.GET("/_cron/commitscanner", basemw.Extend(gaemiddleware.RequireCron), CommitScanner)

	r.GET("/_cron/commitauditor", basemw.Extend(gaemiddleware.RequireCron), CommitAuditor)

	r.GET("/admin/smoketest", basemw, SmokeTest)

	r.GET("/admin/status", templatesmw, Status)

	http.DefaultServeMux.Handle("/", r)
}

// Handler for the index page.
func index(rc *router.Context) {
	templates.MustRender(rc.Context, rc.Writer, "pages/index.html", templates.Args{})
}
