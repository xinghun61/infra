// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Package cron implements handlers for appengine cron targets in this app.
//
// All actual logic related to fleet management should be implemented in the
// main fleet API. These handlers should only encapsulate the following bits of
// logic:
// - Calling other API as the appengine service account user.
// - Translating luci-config driven admin task parameters.
package cron

import (
	"errors"
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

// InstallHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers can only be called by appengine's cron service.
func InstallHandlers(r *router.Router, mw router.MiddlewareChain) {
	mw = mw.Extend(gaemiddleware.RequireCron)
	r.GET("/internal/cron/prune-expired", mw, errHandler(pruneExpired))
}

// errHandler wraps a handler function that returns errors.
func errHandler(f func(*router.Context) error) router.Handler {
	return func(ctx *router.Context) {
		if err := f(ctx); err != nil {
			logging.Errorf(ctx.Context, "handler returned error: %s", err)
			http.Error(ctx.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

func pruneExpired(ctx *router.Context) (err error) {
	defer func() {
		pruneExpiredTick.Add(ctx.Context, 1, err == nil)
	}()
	return errors.New("not implemented")
}
