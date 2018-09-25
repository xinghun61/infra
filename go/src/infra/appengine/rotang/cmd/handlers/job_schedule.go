package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// JobSchedule schedules new shifts for enabled rotas.
func (h *State) JobSchedule(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	now := clock.Now(ctx.Context)
	configs, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	for _, cfg := range configs {
		if err := h.scheduleShifts(ctx.Context, cfg, now); err != nil {
			logging.Warningf(ctx.Context, "scheduleShifts(ctx, _, %v) for rota: %q failed: %v", now, cfg.Config.Name, err)
		}
	}
}

func (h *State) scheduleShifts(ctx context.Context, cfg *rotang.Configuration, t time.Time) error {
	if cfg.Config.Expiration == 0 || !cfg.Config.Enabled {
		logging.Infof(ctx, "scheduling of shifts for rota: %q disabled.", cfg.Config.Name)
		return nil
	}
	if len(cfg.Config.Shifts.Shifts) == 0 {
		return status.Errorf(codes.InvalidArgument, "no shifts configured for rota: %q", cfg.Config.Name)
	}
	shifts, err := h.shiftStore(ctx).AllShifts(ctx, cfg.Config.Name)
	if err != nil {
		return err
	}
	var nrShifts int
	for _, s := range shifts {
		if s.EndTime.Before(t) {
			continue
		}
		nrShifts++
	}
	if nrShifts/len(cfg.Config.Shifts.Shifts) > cfg.Config.Expiration {
		logging.Infof(ctx, "still enough shifts scheduled for rota: %q", cfg.Config.Name)
		return nil
	}
	g, err := h.generators.Fetch(cfg.Config.Shifts.Generator)
	if err != nil {
		return err
	}
	var ms []rotang.Member
	for _, m := range cfg.Members {
		rm, err := h.memberStore(ctx).Member(ctx, m.Email)
		if err != nil {
			return err
		}
		ms = append(ms, *rm)
	}
	ss, err := g.Generate(cfg, t, shifts, ms, cfg.Config.ShiftsToSchedule)
	if err != nil {
		return err
	}
	return h.shiftStore(ctx).AddShifts(ctx, cfg.Config.Name, ss)
}
