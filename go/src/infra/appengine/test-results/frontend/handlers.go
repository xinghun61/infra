// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"html/template"
	"net/http"
	"time"

	"google.golang.org/appengine"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
)

const (
	monitoringQueueName = "monitoring"
	deleteKeysQueueName = "delete-keys"

	deleteKeysPath = "/internal/delete-keys"

	// monitoringPath is the tsmon and event_mon monitoring path.
	// It should be kept in sync with the Python implementation.
	monitoringPath = "/internal/v2/monitoring/upload"
)

func init() {
	r := router.New()

	baseMW := gaemiddleware.BaseProd()
	getMW := baseMW.Extend(templatesMiddleware())

	gaemiddleware.InstallHandlers(r, baseMW)

	r.GET("/testfile", getMW, getHandler)
	r.GET("/testfile/", getMW, getHandler)
	r.POST("/testfile/upload", baseMW.Extend(withParsedUploadForm), uploadHandler)

	r.GET("/builders", baseMW, getBuildersHandler)
	r.GET("/updatebuilders", baseMW, updateBuildersHandler)
	r.GET("/builderstate", baseMW, getBuilderStateHandler)
	r.GET("/updatebuilderstate", baseMW, updateBuilderStateHandler)

	r.POST(
		deleteKeysPath,
		baseMW.Extend(gaemiddleware.RequireTaskQueue(deleteKeysQueueName)),
		deleteKeysHandler,
	)

	r.GET("/revision_range", baseMW, revisionHandler)

	http.DefaultServeMux.Handle("/", r)
}

// templatesMiddleware returns the templates middleware.
func templatesMiddleware() router.Middleware {
	return templates.WithTemplates(&templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: appengine.IsDevAppServer(),
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

	if err := datastore.Get(c).Delete(dkeys); err != nil {
		logging.WithError(err).Errorf(c, "deleteKeysHandler")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}
