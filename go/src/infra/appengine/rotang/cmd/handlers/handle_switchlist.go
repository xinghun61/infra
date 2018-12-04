package handlers

import (
	"net/http"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

// HandleRotaSwitchList lists rotations not yest switched over.
func (h *State) HandleRotaSwitchList(ctx *router.Context) {
	args, err := h.listRotations(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/switchlist.html", args)
}
