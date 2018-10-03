package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// JobEventUpdate reads calendar Events and updaes shifts accordingly.
func (h *State) JobEventUpdate(ctx *router.Context) {
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
		if err := h.eventUpdate(ctx, cfg, now); err != nil {
			logging.Warningf(ctx.Context, "eventUpdate(ctx, _, %v) for rota: %q failed: %v", now, cfg.Config.Name, err)
		}
	}
}

func (h *State) eventUpdate(ctx *router.Context, cfg *rotang.Configuration, t time.Time) error {
	if cfg.Config.Expiration == 0 || !cfg.Config.Enabled {
		logging.Infof(ctx.Context, "updating of shifts for rota: %q disabled.", cfg.Config.Name)
		return nil
	}
	if len(cfg.Config.Shifts.Shifts) == 0 {
		return status.Errorf(codes.InvalidArgument, "no shifts configured for rota: %q", cfg.Config.Name)
	}

	shifts, err := h.shiftStore(ctx.Context).AllShifts(ctx.Context, cfg.Config.Name)
	if err != nil {
		return err
	}

	for _, s := range shifts {
		if s.EndTime.Before(t) {
			continue
		}
		resShift, err := h.calendar.Event(ctx, cfg, &s)
		if err != nil {
			return err
		}
		if shiftsEqual(s, *resShift) {
			continue
		}
		if err = h.shiftStore(ctx.Context).UpdateShift(ctx.Context, cfg.Config.Name, resShift); err != nil {
			return err
		}
	}

	return nil
}

func shiftsEqual(a, b rotang.ShiftEntry) bool {
	if a.Name != b.Name ||
		a.EvtID != b.EvtID ||
		!a.StartTime.Equal(b.StartTime) ||
		!a.EndTime.Equal(b.EndTime) ||
		len(a.OnCall) != len(b.OnCall) {
		return false
	}
	for i, o := range a.OnCall {
		if o.Email != b.OnCall[i].Email || o.ShiftName != b.OnCall[i].ShiftName {
			return false
		}
	}
	return true
}
