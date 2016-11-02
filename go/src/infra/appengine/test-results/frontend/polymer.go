// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
)

// polymerHandler is the HTTP handler for requests to pages that are part of the
// Polymer app.
func polymerHandler(ctx *router.Context) {
	templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{
		"IsDevAppServer": info.IsDevAppServer(ctx.Context),
	})
}
