// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerritpoller implements the Tricium Gerrit poller.
package gerritpoller

import (
	"net/http"

	"github.com/luci/luci-go/server/router"

	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.GET("/gerrit-poller/internal/poll", base, pollHandler)

	http.DefaultServeMux.Handle("/", r)
}
