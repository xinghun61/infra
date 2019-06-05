package handlers

import (
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const externalShift = "external"

// JobExternal updates the external rotations shifts.
func (h *State) JobExternal(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	cfgs, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	for _, cfg := range cfgs {
		if !cfg.Config.External {
			continue
		}
		logging.Infof(ctx.Context, "Processing external rota: %q", cfg.Config.Name)
		memberSet := make(map[string]struct{})
		for _, m := range cfg.Members {
			memberSet[m.Email] = struct{}{}
		}
		start := clock.Now(ctx.Context)
		shifts, err := h.calendar.TrooperShifts(ctx, cfg.Config.Calendar, cfg.Config.ExternalMatch, externalShift, start, start.Add(fullDay*14))
		if err != nil && status.Code(err) != codes.NotFound {
			logging.Warningf(ctx.Context, "TrooperShifts(ctx, %q , %q , _, _) failed: %v", cfg.Config.Calendar, cfg.Config.Name, err)
			continue
		}

		shiftStore := h.shiftStore(ctx.Context)
		for _, s := range shifts {
			logging.Infof(ctx.Context, "%s: Processing shift: %v", cfg.Config.Name, s)
			if err := h.handleExternalMembers(ctx.Context, cfg, &s); err != nil {
				logging.Warningf(ctx.Context, "handleExternalMember failed: %v")
				continue
			}
			if err := shiftStore.UpdateShift(ctx.Context, cfg.Config.Name, &s); err != nil {
				if status.Code(err) != codes.NotFound {
					logging.Warningf(ctx.Context, "UpdateShift(_, %q, %v) failed: %v", cfg.Config.Name, s, err)
					continue
				}
				if err := shiftStore.AddShifts(ctx.Context, cfg.Config.Name, []rotang.ShiftEntry{s}); err != nil {
					logging.Warningf(ctx.Context, "AddShift(_, %q, %v) failed: %v", cfg.Config.Name, []rotang.ShiftEntry{s}, err)
				}
				logging.Infof(ctx.Context, "%s: Added shift: %v", cfg.Config.Name, s)
			}
			logging.Infof(ctx.Context, "%s: UpdateShift: %v worked fine", cfg.Config.Name, s)
		}
	}
}

func (h *State) handleExternalMembers(ctx context.Context, cfg *rotang.Configuration, s *rotang.ShiftEntry) error {
	memberSet := make(map[string]struct{})
	for _, m := range cfg.Members {
		memberSet[m.Email] = struct{}{}
	}

	memberStore := h.memberStore(ctx)
	for _, o := range s.OnCall {
		if _, ok := memberSet[o.Email]; !ok {
			if _, err := memberStore.Member(ctx, o.Email); err != nil {
				if status.Code(err) != codes.NotFound {
					return err
				}
				if err := memberStore.CreateMember(ctx, &rotang.Member{
					Email: o.Email,
				}); err != nil {
					return err
				}
			}
			h.configStore(ctx).AddRotaMember(ctx, cfg.Config.Name, &rotang.ShiftMember{
				ShiftName: externalShift,
				Email:     o.Email,
			})
		}
	}
	return nil
}
