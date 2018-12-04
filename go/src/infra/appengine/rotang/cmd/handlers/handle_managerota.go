// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"net/http"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

// HandleManageRota handles the rota management interface.
func (h *State) HandleManageRota(ctx *router.Context) {
	args, err := h.listRotations(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/managerota.html", args)
}
