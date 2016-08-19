// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"io"
	"net/http"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	"infra/appengine/test-results/builderstate"
)

// refreshFunc is the function that is called to update cached data
// or on cache miss.
// It is global to allow mocking in tests.
var refreshFunc = builderstate.RefreshCache

// getBuilderStateHandler gets data from the builder state memcache
// and serves it as JSON.
func getBuilderStateHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	item, err := memcache.Get(c).Get(builderstate.MemcacheKey)

	if err != nil {
		item, err = refreshFunc(c)
		if err != nil {
			if err == memcache.ErrCacheMiss {
				err = fmt.Errorf("builderstate: builder data not generated: %v", err)
			}
			logging.WithError(err).Errorf(c, "getBuilderStateHandler")
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	n, err := w.Write(item.Value())

	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"n":              n,
			"bytes":          item.Value(),
		}.Errorf(c, "getBuilderStateHandler: error writing HTTP response")
	}
}

// updateBuilderStateHandler refreshes data in the builder state
// memcache.
func updateBuilderStateHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	_, err := refreshFunc(c)

	if err != nil {
		logging.Errorf(c, err.Error())
		w.WriteHeader(http.StatusInternalServerError)
		io.WriteString(w, err.Error())
		return
	}

	n, err := io.WriteString(w, "OK")

	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"n":              n,
		}.Errorf(c, "updateBuilderStateHandler: error writing HTTP response")
	}
}
