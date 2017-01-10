// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package launcher implements the Tricium launcher.
package launcher

import (
	"net/http"

	"github.com/luci/luci-go/server/router"

	"infra/tricium/appengine/common"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	r.POST("/launcher/internal/queue", base, queueHandler)

	http.DefaultServeMux.Handle("/", r)
}
