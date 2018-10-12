package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

const (
	// importDuration specifies how far back to go
	// when importing calendar events.
	importDuration = 365 * 24 * time.Hour
)

// HandleShiftImport saves rotation to backend storage.
func (h *State) HandleShiftImport(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		http.Error(ctx.Writer, "no rota provided", http.StatusNotFound)
		return
	}
	rota, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if len(rota) != 1 {
		http.Error(ctx.Writer, "expected only one rota to be returned", http.StatusInternalServerError)
		return
	}

	if !adminOrOwner(ctx, rota[0]) {
		http.Error(ctx.Writer, "not owner of the rota", http.StatusForbidden)
		return
	}

	// Adding in a year to the end just to make sure we get all events.
	// Presuming nobody would schedule for longar than that.
	shifts, err := h.calendar.Events(ctx, rota[0], time.Now().Add(-importDuration), time.Now().Add(importDuration))
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if ctx.Request.FormValue("store") == "true" {
		memberSet := make(map[string]struct{})
		for _, m := range rota[0].Members {
			memberSet[m.Email] = struct{}{}
		}
		for i, s := range shifts {
			// Pretty common when going back to have users not part of the rota members anymore.
			var newOncall []rotang.ShiftMember
			for _, o := range s.OnCall {
				if _, ok := memberSet[o.Email]; !ok {
					logging.Infof(ctx.Context, "member: %q not a member of rota: %q", o.Email, rota[0].Config.Name)
					continue
				}
				newOncall = append(newOncall, o)
			}
			shifts[i].OnCall = newOncall
		}
		if err := h.shiftStore(ctx.Context).AddShifts(ctx.Context, rota[0].Config.Name, shifts); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	templates.MustRender(ctx.Context, ctx.Writer, "pages/shiftimport.html", templates.Args{"Shifts": shifts, "Name": rotaName, "Submitted": ctx.Request.FormValue("store")})
}
