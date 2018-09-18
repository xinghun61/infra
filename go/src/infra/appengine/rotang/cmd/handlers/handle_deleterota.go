package handlers

import (
	"net/http"

	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

// HandleDeleteRota handles deletion of a rotation configuration
func (h *State) HandleDeleteRota(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleDeleteRota handles only POST requests", http.StatusBadRequest)
		return
	}

	if err := ctx.Request.ParseForm(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		http.Error(ctx.Writer, "`name` not set", http.StatusBadRequest)
		return
	}
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if len(rotas) != 1 {
		http.Error(ctx.Writer, "Unexpected number of rotations returned", http.StatusInternalServerError)
		return
	}
	rota := rotas[0]

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil {
		http.Error(ctx.Writer, "login required", http.StatusForbidden)
		return
	}

	isOwner := false
	for _, o := range rota.Config.Owners {
		if o == usr.Email {
			isOwner = true
			break
		}
	}

	if !isOwner {
		http.Error(ctx.Writer, "not in the rotation owners", http.StatusForbidden)
		return
	}

	if err := h.configStore(ctx.Context).DeleteRotaConfig(ctx.Context, rotaName); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	http.Redirect(ctx.Writer, ctx.Request, h.selfURL+"/managerota", http.StatusOK)
}
