package handlers

import (
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

// HandleRotaSwitch handles the rotation switch page.
func (h *State) HandleRotaSwitch(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	args, err := h.modifyRotation(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	args["safe"], err = h.safeToMigrateCalendar(ctx.Context, args["Config"].(*rotang.Configuration))
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/switchrota.html", args)
}

// safeToMigrateCalendar checks if the calendar is shared among multiple rotations.
// If so it checks if the provided configuration is the last one to migrate.
func (h *State) safeToMigrateCalendar(ctx context.Context, cfg *rotang.Configuration) (bool, error) {
	rotas, err := h.configStore(ctx).RotaConfig(ctx, "")
	if err != nil {
		return false, err
	}
	for _, rota := range rotas {
		if rota.Config.Name == cfg.Config.Name {
			continue
		}
		if rota.Config.Calendar == cfg.Config.Calendar {
			if !rota.Config.Enabled {
				return false, nil
			}
		}
	}
	return true, nil
}
