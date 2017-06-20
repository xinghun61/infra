// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements the App Engine based HTTP server
// behind test-results.appspot.com.
package frontend

import (
	"encoding/json"
	"html/template"
	"net/http"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
)

const (
	monitoringQueueName = "monitoring"
	deleteKeysQueueName = "delete-keys"

	deleteKeysPath = "/internal/delete-keys"

	// testResultMonPath is the event_mon monitoring endpoint path. It should be
	// kept in sync with the Python implementation.
	testResultMonPath = "/internal/monitoring/test_res/upload"
)

func init() {
	r := router.New()

	baseMW := gaemiddleware.BaseProd()
	getMW := baseMW.Extend(templatesMiddleware())
	authMW := baseMW.Extend(
		auth.Authenticate(&server.OAuth2Method{Scopes: []string{server.EmailScope}}),
	)

	gaemiddleware.InstallHandlers(r)

	// Endpoints used by end users.
	r.GET("/", getMW, polymerHandler)
	r.GET("/home", getMW, polymerHandler)
	r.GET("/flakiness", getMW, polymerHandler)
	r.GET("/flakiness/*path", getMW, polymerHandler)

	// TODO(sergiyb): This endpoint may return JSON if supplied parameters select
	// exactly one test file, but normally returns HTML. Consider separating JSON
	// output into a /data/ endpoint, but make sure that all clients are updated.
	r.GET("/testfile", getMW, getHandler)
	r.GET("/revision_range", baseMW, revisionHandler)

	// POST endpoints.
	r.POST("/testfile/upload", authMW.Extend(withParsedUploadForm), uploadHandler)

	r.POST(
		deleteKeysPath,
		baseMW.Extend(gaemiddleware.RequireTaskQueue(deleteKeysQueueName)),
		deleteKeysHandler,
	)

	// Endpoints that return JSON and not expected to be used by humans.
	r.GET("/data/builders", baseMW, getBuildersHandler)
	r.GET("/data/test_flakiness/list", baseMW, testFlakinessListHandler)
	r.GET("/data/test_flakiness/groups", baseMW, testFlakinessGroupsHandler)
	r.GET("/data/test_flakiness/data", baseMW, testFlakinessDataHandler)

	http.DefaultServeMux.Handle("/", r)
}

// templatesMiddleware returns the templates middleware.
func templatesMiddleware() router.Middleware {
	return templates.WithTemplates(&templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: info.IsDevAppServer,
		FuncMap: template.FuncMap{
			"timeParams": func(t time.Time) string {
				return t.Format(paramsTimeFormat)
			},
			"timeJS": func(t time.Time) int64 {
				return t.Unix() * 1000
			},
		},
	})
}

func reportOldEndpoint(c *router.Context, next router.Handler) {
	logging.Debugf(c.Context, "Detected request to a deprecated endpoint %s", c.Request.URL)
	next(c)
}

// deleteKeysHandler is task queue handler for deleting keys.
func deleteKeysHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	keys := struct {
		Keys []string `json:"keys"`
	}{}
	if err := json.NewDecoder(r.Body).Decode(&keys); err != nil {
		logging.WithError(err).Errorf(c, "deleteKeysHandler: error decoding")
		w.WriteHeader(http.StatusOK) // Prevent retrying with the same r.Body.
		return
	}

	dkeys := make([]*datastore.Key, 0, len(keys.Keys))
	for _, k := range keys.Keys {
		dk, err := datastore.NewKeyEncoded(k)
		if err != nil {
			logging.WithError(err).Errorf(c, "deleteKeysHandler")
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		dkeys = append(dkeys, dk)
	}

	if err := datastore.Delete(c, dkeys); err != nil {
		logging.WithError(err).Errorf(c, "deleteKeysHandler")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}
