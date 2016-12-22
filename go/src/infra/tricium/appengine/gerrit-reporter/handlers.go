// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package handlers implements HTTP handlers for the gerrit-reporter module.
package handlers

import (
	"net/http"

	"github.com/luci/luci-go/server/router"

	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/gerrit-reporter/queue", base, queueHandler)

	http.DefaultServeMux.Handle("/", r)
}

func queueHandler(c *router.Context) {
	// TODO(emso): Process request and report event to Gerrit
}
