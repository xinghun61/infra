// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"net/http"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"infra/tricium/appengine/common/config"
)

// UpdateHandler is the HTTP router handler for handling cron-triggered
// configuration update requests.
func UpdateHandler(ctx *router.Context) {
	h := ctx.Writer
	c, cancel := context.WithTimeout(ctx.Context, 9*time.Minute)
	defer cancel()
	if err := config.UpdateAllConfigs(c); err != nil {
		logging.WithError(err).Errorf(c, "Failed to update configs.")
		h.WriteHeader(http.StatusInternalServerError)
		return
	}
	h.WriteHeader(http.StatusOK)
}
