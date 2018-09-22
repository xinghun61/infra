// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/gae/service/user"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleManageRota handles the rota management interface.
func (h *State) HandleManageRota(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	usr := user.Current(ctx.Context)
	if usr == nil {
		http.Error(ctx.Writer, "not logged in", http.StatusProxyAuthRequired)
		return
	}

	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil && status.Code(err) != codes.NotFound {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	var permRotas []*rotang.Configuration
	for _, rota := range rotas {
		for _, m := range rota.Config.Owners {
			if usr.Email == m {
				permRotas = append(permRotas, rota)
			}
		}
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/managerota.html", templates.Args{"Rotas": permRotas})
}
