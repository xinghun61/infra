// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang/pkg/datastore"
	"net/http"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

// HandleList lists all rotations in store.
func (h *State) HandleList(ctx *router.Context) {
	ds, err := datastore.New(ctx.Context)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	rotas, err := ds.RotaConfig(ctx.Context, "")
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/list.html", templates.Args{"Rotas": rotas})
}
