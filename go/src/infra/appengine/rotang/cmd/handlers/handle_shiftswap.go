package handlers

import (
	"context"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleShiftSwap is used by the rota-shift-swap element
// for swapping shifts.
func (h *State) HandleShiftSwap(ctx *router.Context) {
	cfg, shifts, err := h.swapSetup(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		http.Error(ctx.Writer, "login required", http.StatusForbidden)
		return
	}
	var member *rotang.ShiftMember
	for _, m := range cfg.Members {
		if usr.Email == m.Email {
			member = &m
			break
		}
	}
	if member == nil {
		http.Error(ctx.Writer, "not a rotation member", http.StatusForbidden)
		return
	}
	if err := h.shiftChanges(ctx.Context, cfg, shifts, member); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
}

func (h *State) swapSetup(ctx *router.Context) (*rotang.Configuration, *RotaShifts, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, nil, err
	}

	if ctx.Request.Method != "POST" {
		return nil, nil, status.Errorf(codes.InvalidArgument, "Only POST requests supported")
	}

	var res RotaShifts
	if err := json.NewDecoder(ctx.Request.Body).Decode(&res); err != nil {
		return nil, nil, err
	}

	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, res.Rota)
	if err != nil {
		return nil, nil, err
	}
	if len(rotas) != 1 {
		return nil, nil, status.Errorf(codes.Internal, "expected only one rota to be returned")
	}

	return rotas[0], &res, nil
}

func (h *State) shiftChanges(ctx context.Context, cfg *rotang.Configuration, ss *RotaShifts, usr *rotang.ShiftMember) error {
	if ss == nil || cfg == nil || usr == nil {
		return status.Errorf(codes.InvalidArgument, "cfg, ss and usr must be set.")
	}

	var us []rotang.ShiftEntry
	for _, ss := range ss.SplitShifts {
		for _, s := range ss.Shifts {
			us = append(us, s)
		}
	}

	shiftStore := h.shiftStore(ctx)
	for _, s := range us {
		origShift, err := shiftStore.Shift(ctx, cfg.Config.Name, s.StartTime)
		if err != nil {
			return err
		}
		s.EvtID = origShift.EvtID
		logging.Infof(ctx, "origShift: %v, update: %v, origUTC: %v,updateUTC: %v", origShift, s, origShift.EndTime.UTC(), s.EndTime.UTC())
		if shiftUserDiff(origShift, &s, *usr) {
			if s.Comment == "" {
				return status.Errorf(codes.InvalidArgument, "please provide a comment")
			}
			if err := shiftStore.UpdateShift(ctx, cfg.Config.Name, &s); err != nil {
				return err
			}
		}
	}
	return nil
}

// shiftUserDiff checks that the changes to the shifts are either in the comment
// or related to the provided user.
func shiftUserDiff(original, update *rotang.ShiftEntry, user rotang.ShiftMember) bool {
	if !original.EndTime.UTC().Equal(update.EndTime.UTC()) ||
		original.Name != update.Name {
		return false
	}

	cmpMember := func(o, u rotang.ShiftMember) bool {
		if o.Email != u.Email || o.ShiftName != u.ShiftName {
			return false
		}
		return true
	}

	// Possible changes.
	// Same length - One entry set to user.
	// Original shorter - Added entry should be user.
	// Update shorter - Removed entry should be user.
	switch {
	case len(original.OnCall) == len(update.OnCall):
		var changes int
		for i, o := range original.OnCall {
			if !cmpMember(o, update.OnCall[i]) {
				if update.OnCall[i].Email == user.Email &&
					update.OnCall[i].ShiftName == user.ShiftName {
					changes++
				}
			}
		}
		if changes != 1 {
			return false
		}
	case len(original.OnCall) < len(update.OnCall):
		if len(update.OnCall)-len(original.OnCall) != 1 {
			return false
		}
		if !(update.OnCall[len(update.OnCall)-1].Email == user.Email &&
			update.OnCall[len(update.OnCall)-1].ShiftName == user.ShiftName) {
			return false
		}
		for i, o := range original.OnCall {
			if !cmpMember(o, update.OnCall[i]) {
				return false
			}
		}
	case len(original.OnCall) > len(update.OnCall):
		if len(original.OnCall)-len(update.OnCall) != 1 {
			return false
		}
		var res []rotang.ShiftMember
		for _, o := range original.OnCall {
			if o.Email == user.Email &&
				o.ShiftName == user.ShiftName {
				continue
			}
			res = append(res, o)
		}
		if len(res) != len(update.OnCall) {
			return false
		}
		for i, o := range res {
			if !cmpMember(o, update.OnCall[i]) {
				return false
			}
		}

	}
	return true
}
