package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"io"
	"net/http"
	"time"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	// importDuration specifies how far back to go
	// when importing calendar events.
	importDuration = 365 * 24 * time.Hour
)

// HandleShiftImportJSON imort shifts from  legacy calendar.
func (h *State) HandleShiftImportJSON(ctx *router.Context) {
	rota, shifts, err := h.importShifts(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	var res bytes.Buffer
	if err := json.NewEncoder(&res).Encode(shifts); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if ctx.Request.FormValue("store") == "true" {
		if err := h.submitShifts(ctx, rota, shifts); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		return
	}
	io.Copy(ctx.Writer, &res)
}

func (h *State) submitShifts(ctx *router.Context, rota *rotang.Configuration, shifts []rotang.ShiftEntry) error {
	if rota.Config.Enabled {
		return status.Errorf(codes.FailedPrecondition, "imports not supported for enabled rotations")
	}
	cs, err := h.shiftStore(ctx.Context).AllShifts(ctx.Context, rota.Config.Name)
	if err != nil {
		if status.Code(err) != codes.NotFound {
			return err
		}
	}
	if len(cs) != 0 {
		logging.Infof(ctx.Context, "shift exists for rota: %q, clearing before import", rota.Config.Name)
		if err := h.shiftStore(ctx.Context).DeleteAllShifts(ctx.Context, rota.Config.Name); err != nil {
			return err
		}
	}
	memberSet := make(map[string]struct{})
	for _, m := range rota.Members {
		memberSet[m.Email] = struct{}{}
	}
	for i, s := range shifts {
		// Pretty common when going back to have users not part of the rota members anymore.
		var newOncall []rotang.ShiftMember
		for _, o := range s.OnCall {
			if _, ok := memberSet[o.Email]; !ok {
				logging.Infof(ctx.Context, "member: %q not a member of rota: %q", o.Email, rota.Config.Name)
				continue
			}
			newOncall = append(newOncall, o)
		}
		shifts[i].OnCall = newOncall
	}
	if err := h.shiftStore(ctx.Context).AddShifts(ctx.Context, rota.Config.Name, shifts); err != nil {
		return err
	}
	return nil
}

func (h *State) importShifts(ctx *router.Context) (*rotang.Configuration, []rotang.ShiftEntry, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, nil, err
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		return nil, nil, status.Errorf(codes.InvalidArgument, "no rota provied")
	}
	rota, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		return nil, nil, err
	}
	if len(rota) != 1 {
		return nil, nil, status.Errorf(codes.Internal, "expected only one rota to be returned")
	}

	if !adminOrOwner(ctx, rota[0]) {
		return nil, nil, status.Errorf(codes.PermissionDenied, "not rotation owner")
	}

	// Adding in a year to the end just to make sure we get all events.
	// Presuming nobody would schedule for longar than that.
	shifts, err := h.calendar.Events(ctx, rota[0], time.Now().Add(-importDuration), time.Now().Add(importDuration))
	if err != nil {
		return nil, nil, err
	}
	return rota[0], shifts, nil
}
