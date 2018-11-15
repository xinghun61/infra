package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// RotaShifts mirrors the `shiftcurrent-element` RotaShifts structure.
type RotaShifts struct {
	Rota        string
	SplitShifts []SplitShifts
}

// SplitShifts mirrors the `shiftcurrent-element` SplitShifts structure.
type SplitShifts struct {
	Name    string
	Members []string
	Shifts  []rotang.ShiftEntry
}

// HandleManageShifts presents the shift management page.
func (h *State) HandleManageShifts(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	now := clock.Now(ctx.Context)

	tp, err := h.manageShiftsGET(ctx, now)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/manageshifts.html", tp)
}

func (h *State) manageShiftsGET(ctx *router.Context, t time.Time) (templates.Args, error) {
	if err := ctx.Request.ParseForm(); err != nil {
		return nil, err
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		return nil, status.Errorf(codes.InvalidArgument, "`name` not set")
	}
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		return nil, err
	}

	if len(rotas) != 1 {
		return nil, status.Errorf(codes.OutOfRange, "unexpected number of rotations returned")
	}
	rota := rotas[0]

	if !adminOrOwner(ctx, rota) {
		return nil, status.Errorf(codes.Unauthenticated, "not admin or owner")
	}

	shifts, err := h.shiftStore(ctx.Context).AllShifts(ctx.Context, rota.Config.Name)
	if err != nil && status.Code(err) != codes.NotFound {
		return nil, err
	}

	history, current := handleShifts(shifts, rota.Members, t)

	// Since this is to be presented in a UI it might be nice
	// to have it ordered by start time of the ShiftSplit.
	arrangeShiftByStart(rota, history)
	arrangeShiftByStart(rota, current)

	hRota := RotaShifts{
		Rota:        rotaName,
		SplitShifts: history,
	}
	cRota := RotaShifts{
		Rota:        rotaName,
		SplitShifts: current,
	}

	var hBuf, cBuf bytes.Buffer
	hEnc := json.NewEncoder(&hBuf)
	if err := hEnc.Encode(hRota); err != nil {
		return nil, err
	}
	cEnc := json.NewEncoder(&cBuf)
	if err := cEnc.Encode(cRota); err != nil {
		return nil, err
	}

	return templates.Args{
		"Rota":    rota.Config.Name,
		"History": hBuf.String(),
		"Current": cBuf.String(),
	}, nil
}

func arrangeShiftByStart(cfg *rotang.Configuration, ss []SplitShifts) {
	for i, s := range cfg.Config.Shifts.Shifts {
		for j, split := range ss {
			if split.Name == s.Name {
				ss[i], ss[j] = ss[j], ss[i]
			}
		}
	}
}

func handleShifts(in []rotang.ShiftEntry, ms []rotang.ShiftMember, t time.Time) ([]SplitShifts, []SplitShifts) {
	var hs, cu []rotang.ShiftEntry
	for _, s := range in {
		if s.EndTime.Before(t) {
			hs = append(hs, s)
			continue
		}
		cu = append(cu, s)
	}

	history := makeSplitShifts(hs, ms)
	current := makeSplitShifts(cu, ms)

	return history, current
}

func makeSplitShifts(in []rotang.ShiftEntry, ms []rotang.ShiftMember) []SplitShifts {
	mMap := make(map[string][]string)
	for _, m := range ms {
		mMap[m.ShiftName] = append(mMap[m.ShiftName], m.Email)
	}
	ssMap := make(map[string][]rotang.ShiftEntry)
	for _, s := range in {
		ssMap[s.Name] = append(ssMap[s.Name], s)
	}
	var res []SplitShifts
	for k, v := range ssMap {
		res = append(res, SplitShifts{
			Name:    k,
			Members: mMap[k],
			Shifts:  v,
		})
	}
	return res
}

// shiftSetup contains code shared between the shift management handlers.
func (h *State) shiftSetup(ctx *router.Context) (*rotang.Configuration, *RotaShifts, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, nil, err
	}

	if ctx.Request.Method != "POST" {
		return nil, nil, status.Errorf(codes.InvalidArgument, "Only POST requests supported")
	}

	if ctx.Request.Body == nil {
		return nil, nil, status.Error(codes.InvalidArgument, "request Body empty")
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

	rota := rotas[0]

	if !adminOrOwner(ctx, rota) {
		http.Error(ctx.Writer, "not owner or admin of rotation", http.StatusForbidden)
		return nil, nil, status.Errorf(codes.Unauthenticated, "not owner of rotation or admin")
	}
	return rota, &res, nil
}

// HandleShiftGenerate saves generated shifts.
func (h *State) HandleShiftGenerate(ctx *router.Context) {
	cfg, ss, err := h.shiftSetup(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if err := h.handleGeneratedShifts(ctx, cfg, ss); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
}

func (h *State) handleGeneratedShifts(ctx *router.Context, cfg *rotang.Configuration, ss *RotaShifts) error {
	shiftStorer := h.shiftStore(ctx.Context)

	var shifts []rotang.ShiftEntry
	for _, split := range ss.SplitShifts {
		shifts = append(shifts, split.Shifts...)
	}

	if err := shiftStorer.AddShifts(ctx.Context, cfg.Config.Name, shifts); err != nil {
		return err
	}

	if !cfg.Config.Enabled {
		logging.Infof(ctx.Context, "calendar not updated for rota: %q due to not being enabled")
		return nil
	}
	resShifts, err := h.calendar.CreateEvent(ctx, cfg, shifts)
	if err != nil {
		return err
	}
	for _, s := range resShifts {
		if err := shiftStorer.UpdateShift(ctx.Context, cfg.Config.Name, &s); err != nil {
			return err
		}
	}
	return nil
}

// HandleShiftUpdate handles shift updates.
func (h *State) HandleShiftUpdate(ctx *router.Context) {
	cfg, ss, err := h.shiftSetup(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if err := h.handleUpdatedShifts(ctx, cfg, ss); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
}

func (h *State) handleUpdatedShifts(ctx *router.Context, cfg *rotang.Configuration, ss *RotaShifts) error {
	shiftStorer := h.shiftStore(ctx.Context)

	var lastShift time.Time
	for _, split := range ss.SplitShifts {
		for _, shift := range split.Shifts {
			us := &shift
			if cfg.Config.Enabled {
				var err error
				if us, err = h.calendar.UpdateEvent(ctx, cfg, &shift); err != nil {
					return err
				}
			}
			if err := shiftStorer.UpdateShift(ctx.Context, cfg.Config.Name, us); err != nil {
				return err
			}
			if lastShift.After(shift.StartTime) {
				continue
			}
			lastShift = shift.StartTime
		}
	}

	as, err := shiftStorer.ShiftsFromTo(ctx.Context, cfg.Config.Name, lastShift, time.Time{})
	if err != nil {
		return err
	}
	for _, s := range as {
		if err := shiftStorer.DeleteShift(ctx.Context, cfg.Config.Name, s.StartTime); err != nil {
			return err
		}
		if cfg.Config.Enabled {
			if err := h.calendar.DeleteEvent(ctx, cfg, &s); err != nil {
				return err
			}
		}
	}
	return nil
}
