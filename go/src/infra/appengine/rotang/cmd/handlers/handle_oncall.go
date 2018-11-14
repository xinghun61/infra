package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleOncall handles the current oncall page.
func (h *State) HandleOncall(ctx *router.Context) {
	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		http.Error(ctx.Writer, "not logged in", http.StatusForbidden)
		return
	}

	now := clock.Now(ctx.Context)
	rota := ctx.Params.ByName("name")

	var tas templates.Args
	var err error
	if rota == "" {
		tas, err = h.genAllRotas(ctx, usr.Email, now)
	} else {
		tas, err = h.genSingleRota(ctx, usr.Email, ctx.Params.ByName("name"), now)
	}
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/oncall.html", tas)
}

func (h *State) genSingleRota(ctx *router.Context, email, rota string, at time.Time) (templates.Args, error) {
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rota)
	if err != nil {
		return nil, err
	}
	if len(rotas) != 1 {
		http.Error(ctx.Writer, "unexpected number of rotations returned", http.StatusInternalServerError)
		return nil, status.Errorf(codes.Internal, "unexpected number of rotations returned")
	}
	rt := rotas[0]

	var mr rotang.ShiftMember
	for _, m := range rt.Members {
		if m.Email == email {
			mr = m
			break
		}
	}

	shifts, err := h.shiftStore(ctx.Context).AllShifts(ctx.Context, rt.Config.Name)
	if err != nil && status.Code(err) != codes.NotFound {
		return nil, err
	}
	_, current := handleShifts(shifts, []rotang.ShiftMember{
		mr}, at)
	arrangeShiftByStart(rt, current)
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(&RotaShifts{
		Rota:        rota,
		SplitShifts: current,
	}); err != nil {
		return nil, err
	}
	var rBuf bytes.Buffer
	rEnc := json.NewEncoder(&rBuf)
	if err := rEnc.Encode([]string{rota}); err != nil {
		return nil, err
	}
	return templates.Args{"User": email, "Rotas": rBuf.String(), "Current": buf.String()}, nil
}

func (h *State) genAllRotas(ctx *router.Context, email string, at time.Time) (templates.Args, error) {
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil {
		return nil, err
	}
	var rotations []string
	for _, r := range rotas {
		rotations = append(rotations, r.Config.Name)
	}
	var rBuf bytes.Buffer
	rEnc := json.NewEncoder(&rBuf)
	if err := rEnc.Encode(rotations); err != nil {
		return nil, err
	}
	return templates.Args{"User": email, "Rotas": rBuf.String()}, nil
}

// OnCallers is the struct used with the `rota-oncall` element.
type OnCallers struct {
	Name  string
	Shift rotang.ShiftEntry
}

// OnCallerRequest is the format used by the `rota-oncall` element for
// requests.
type OnCallerRequest struct {
	Name string
	At   time.Time
}

// HandleOncallJSON returns a JSON representation of oncallers.
// Primarily used by the `rota-oncall` element.
func (h *State) HandleOncallJSON(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleOncallJSON handles POST requests only, req was:", http.StatusBadRequest)
		return
	}

	json, err := h.oncallJSON(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	fmt.Fprintln(ctx.Writer, json)
}

func (h *State) oncallJSON(ctx *router.Context) (string, error) {
	var req []OnCallerRequest
	if err := json.NewDecoder(ctx.Request.Body).Decode(&req); err != nil {
		return "", err
	}

	var res []OnCallers
	ss := h.shiftStore(ctx.Context)
	for _, r := range req {
		if r.Name == "" {
			return h.allOncallJSON(ctx, r.At)
		}
		s, err := ss.Oncall(ctx.Context, r.At, r.Name)
		if err != nil {
			if status.Code(err) != codes.NotFound {
				return "", err
			}
			logging.Warningf(ctx.Context, "Nobody oncall for %q at: %v", r.Name, r.At)
			s = &rotang.ShiftEntry{}
		}
		res = append(res, OnCallers{
			Name:  r.Name,
			Shift: *s,
		})
	}

	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(res); err != nil {
		return "", err
	}

	return buf.String(), nil
}

func (h *State) allOncallJSON(ctx *router.Context, at time.Time) (string, error) {
	cs, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil {
		return "", nil
	}

	var res []OnCallers
	ss := h.shiftStore(ctx.Context)
	for _, c := range cs {
		s, err := ss.Oncall(ctx.Context, at, c.Config.Name)
		if err != nil {
			if status.Code(err) != codes.NotFound {
				return "", err
			}
			logging.Warningf(ctx.Context, "Nobody oncall for %q at: %v", c.Config.Name, at)
			s = &rotang.ShiftEntry{}
		}
		if len(s.OnCall) > 0 {
			logging.Infof(ctx.Context, "Rota: %q oncallers: %v", c.Config.Name, s.OnCall)
		}
		res = append(res, OnCallers{
			Name:  c.Config.Name,
			Shift: *s,
		})
	}

	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(res); err != nil {
		return "", err
	}

	return buf.String(), nil
}
