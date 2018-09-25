// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleIndex is the handler used for requests to '/'.
func (h *State) HandleIndex(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	res := []struct {
		Rota      string
		Oncallers []rotang.ShiftMember
	}{}

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{"Rotas": res})
		return
	}
	rotas, err := h.configStore(ctx.Context).MemberOf(ctx.Context, usr.Email)
	if err != nil && status.Code(err) != codes.NotFound {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{"Rotas": rotas, "User": usr})
}
