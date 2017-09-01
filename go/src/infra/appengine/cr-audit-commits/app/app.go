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

// Lets the templates lib know where to load templates from.
func getTemplatesMW() router.Middleware {
	return templates.WithTemplates(&templates.Bundle{
		Loader: templates.FileSystemLoader("templates"),
	})
}

func init() {
	r := router.New()

	// This does not require auth. Needed for index page.
	basemw := standard.Base()

	// This ensures that the route is only accessible to cron jobs.
	cronmw := standard.Base().Extend(gaemiddleware.RequireCron)

	standard.InstallHandlers(r)

	r.GET("/", basemw.Extend(getTemplatesMW()), index)
	r.GET("/_cron/commitscanner", cronmw, CommitScanner)

	http.DefaultServeMux.Handle("/", r)
}

func index(rc *router.Context) {
	templates.MustRender(rc.Context, rc.Writer, "pages/index.html", templates.Args{})
}
