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

// JobEventUpdate reads calendar Events and updates shifts accordingly.
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
	if !cfg.Config.Enabled {
		logging.Infof(ctx.Context, "updating of shifts for rota: %q disabled.", cfg.Config.Name)
		return nil
	}
	if len(cfg.Config.Shifts.Shifts) == 0 {
		return status.Errorf(codes.InvalidArgument, "no shifts configured for rota: %q", cfg.Config.Name)
	}

	shifts, err := h.shiftStore(ctx.Context).ShiftsFromTo(ctx.Context, cfg.Config.Name, t, time.Time{})
	if err != nil {
		return err
	}

	for _, s := range shifts {
		resShift, err := h.calendar.Event(ctx, cfg, &s)
		if err != nil {
			if status.Code(err) == codes.NotFound {
				if err := h.createNonExists(ctx, cfg, s); err != nil {
					return err
				}
				logging.Infof(ctx.Context, "Calendar entry for shift: %v created in calendar due to not existing", s)
				continue
			}
			return err
		}
		if shiftsEqual(s, *resShift) {
			continue
		}
		resShift.Comment = s.Comment
		if err = h.shiftStore(ctx.Context).UpdateShift(ctx.Context, cfg.Config.Name, resShift); err != nil {
			return err
		}
		logging.Infof(ctx.Context, "shift: %v updated from calendar, updated shift: %v", s, *resShift)
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

func (h *State) createNonExists(ctx *router.Context, cfg *rotang.Configuration, shift rotang.ShiftEntry) error {
	shifts, err := h.calendar.CreateEvent(ctx, cfg, []rotang.ShiftEntry{shift})
	if err != nil {
		return err
	}
	if len(shifts) != 1 {
		return status.Errorf(codes.Internal, "wrong number of shifts returned, got: %c expected: %d", len(shifts), 1)
	}
	shift.EvtID = shifts[0].EvtID
	return h.shiftStore(ctx.Context).UpdateShift(ctx.Context, cfg.Config.Name, &shift)
}
