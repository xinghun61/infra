package handlers

import (
	"net/http"

	"go.chromium.org/luci/server/router"
)

// HandleEnableDisable enables/disables rotation configurations.
func (h *State) HandleEnableDisable(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleEnableDisable handles only POST requests", http.StatusBadRequest)
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

	if !adminOrOwner(ctx, rota) {
		http.Error(ctx.Writer, "not in the rotation owners", http.StatusForbidden)
		return
	}

	if rota.Config.Enabled {
		err = h.configStore(ctx.Context).DisableRota(ctx.Context, rota.Config.Name)
	} else {
		err = h.configStore(ctx.Context).EnableRota(ctx.Context, rota.Config.Name)
	}
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	http.Redirect(ctx.Writer, ctx.Request, "/managerota", http.StatusOK)
}
