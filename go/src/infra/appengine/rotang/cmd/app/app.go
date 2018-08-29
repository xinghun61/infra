// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package app sets up the AppEngine routing and h.
package app

import (
	"net/http"

	"infra/appengine/rotang/cmd/handlers"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

const (
	selfURL          = "http://nop2.c.googlers.com:8080"
	oauthCallbackURL = "http://localhost:8080/oauth2callback"
)

func init() {
	r := router.New()
	standard.InstallHandlers(r)
	middleware := standard.Base()

	tmw := middleware.Extend(templates.WithTemplates(&templates.Bundle{
		Loader: templates.FileSystemLoader("../handlers/templates"),
	}))

	h := handlers.New(selfURL, "", oauthCallbackURL)

	r.GET("/", tmw, h.HandleIndex)
	r.GET("/upload", tmw, h.HandleUpload)
	r.GET("/list", tmw, h.HandleList)
	r.POST("/upload", tmw, h.HandleUpload)

	http.DefaultServeMux.Handle("/", r)
}
