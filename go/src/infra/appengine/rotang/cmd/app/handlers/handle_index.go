package handlers

import (
	"net/http"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

// HandleIndex is the handler used for requests to '/'.
func HandleIndex(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{})
}
