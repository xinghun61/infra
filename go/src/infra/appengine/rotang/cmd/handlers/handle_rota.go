// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func cleanOwners(email, ownStr string) ([]string, error) {
	owners := strings.Split(ownStr, ",")
	ownerFound := false
	for i := range owners {
		owners[i] = strings.Join(strings.Fields(owners[i]), "")
		if owners[i] == email {
			ownerFound = true
		}
	}
	if !ownerFound {
		return nil, status.Errorf(codes.NotFound, "current user not in owners")
	}
	return owners, nil
}

func fillIntegers(ctx *router.Context, cfg *rotang.Config) error {
	var err error
	if cfg.Email.DaysBeforeNotify, err = strconv.Atoi(ctx.Request.FormValue("EmailNotify")); err != nil {
		return err
	}
	if cfg.Expiration, err = strconv.Atoi(ctx.Request.FormValue("Expiration")); err != nil {
		return err
	}
	if cfg.ShiftsToSchedule, err = strconv.Atoi(ctx.Request.FormValue("ShiftsToSchedule")); err != nil {
		return err
	}
	if cfg.Shifts.Length, err = strconv.Atoi(ctx.Request.FormValue("shiftLength")); err != nil {
		return err
	}
	if cfg.Shifts.Skip, err = strconv.Atoi(ctx.Request.FormValue("shiftSkip")); err != nil {
		return err
	}
	if cfg.Shifts.ShiftMembers, err = strconv.Atoi(ctx.Request.FormValue("shiftMembers")); err != nil {
		return err
	}
	if cfg.Shifts.StartTime, err = time.Parse("15:04", ctx.Request.FormValue("shiftStart")); err != nil {
		return err
	}

	return nil
}

func fillMembers(ctx *router.Context, memberStore rotang.MemberStorer) ([]rotang.ShiftMember, error) {
	if len(ctx.Request.Form["addEmail"]) != len(ctx.Request.Form["addTZ"]) ||
		len(ctx.Request.Form["addEmail"]) != len(ctx.Request.Form["addName"]) ||
		len(ctx.Request.Form["addEmail"]) != len(ctx.Request.Form["addMemberShiftName"]) ||
		len(ctx.Request.Form["memberName"]) != len(ctx.Request.Form["memberShiftName"]) {
		logging.Infof(ctx.Context, "addEmail: %v addTZ: %v addName: %v", ctx.Request.Form["addEmail"], ctx.Request.Form["addTZ"], ctx.Request.Form["addName"])
		return nil, status.Errorf(codes.InvalidArgument, "Email, TimeZone, Name, memberName and shiftName  must all have a value")
	}

	var members []rotang.ShiftMember
	for i, v := range ctx.Request.Form["addEmail"] {
		if v == "" {
			logging.Warningf(ctx.Context, "skipping user with empty email, name: %q", ctx.Request.Form["addName"][i])
			continue
		}
		loc, err := time.LoadLocation(ctx.Request.Form["addTZ"][i])
		if err != nil {
			loc = time.UTC
		}
		member := rotang.Member{
			Email: v,
			Name:  ctx.Request.Form["addName"][i],
			TZ:    *loc,
		}
		if err := memberStore.CreateMember(ctx.Context, &member); err != nil && status.Code(err) != codes.AlreadyExists {
			return nil, err
		}
		members = append(members, rotang.ShiftMember{
			Email:     v,
			ShiftName: ctx.Request.Form["addMemberShiftName"][i],
		})
	}
	// Update existing rota.
	for i, v := range ctx.Request.Form["memberName"] {
		m, err := memberStore.Member(ctx.Context, v)
		if err != nil {
			return nil, err
		}
		members = append(members, rotang.ShiftMember{
			Email:     m.Email,
			ShiftName: ctx.Request.Form["memberShiftName"][i],
		})
	}
	// When creating a new rota.
	for _, v := range ctx.Request.Form["members"] {
		m, err := memberStore.Member(ctx.Context, v)
		if err != nil {
			return nil, err
		}
		members = append(members, rotang.ShiftMember{
			Email: m.Email,
		})
	}
	return members, nil
}

func fillShifts(ctx *router.Context) ([]rotang.Shift, error) {
	var shifts []rotang.Shift
	addShifts := func(names, durations []string) error {
		if len(names) != len(durations) {
			return status.Errorf(codes.InvalidArgument, "shift names and duration must all have a value")
		}
		for i, v := range names {
			h, err := strconv.Atoi(durations[i])
			if err != nil {
				return err
			}
			shifts = append(shifts, rotang.Shift{
				Name:     v,
				Duration: time.Duration(h) * time.Hour,
			})
		}
		return nil
	}
	if err := addShifts(ctx.Request.Form["shiftName"], ctx.Request.Form["shiftDuration"]); err != nil {
		return nil, err
	}
	if err := addShifts(ctx.Request.Form["addShiftName"], ctx.Request.Form["addShiftDuration"]); err != nil {
		return nil, err
	}
	return shifts, nil
}

// HandleCreateRota creates a new rotation.
func (h *State) HandleCreateRota(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if ctx.Request.Method == "GET" {
		ms, err := h.memberStore(ctx.Context).AllMembers(ctx.Context)
		if err != nil && status.Code(err) != codes.NotFound {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		usr := auth.CurrentUser(ctx.Context)
		if usr == nil || usr.Email == "" {
			http.Error(ctx.Writer, "login required", http.StatusForbidden)
			return
		}
		templates.MustRender(ctx.Context, ctx.Writer, "pages/modifyrota.html",
			templates.Args{"Members": ms, "User": usr})
		return
	}

	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleCreateRota handles GET and POST requests only", http.StatusBadRequest)
		return
	}

	cfg, err := h.handlePOST(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	logging.Infof(ctx.Context, "cfg: %v", cfg)

	if err := h.configStore(ctx.Context).CreateRotaConfig(ctx.Context, cfg); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	http.Redirect(ctx.Writer, ctx.Request, "managerota", http.StatusFound)
}

func (h *State) handlePOST(ctx *router.Context) (*rotang.Configuration, error) {
	if err := ctx.Request.ParseForm(); err != nil {
		return nil, err
	}

	members, err := fillMembers(ctx, h.memberStore(ctx.Context))
	if err != nil {
		return nil, err
	}

	shifts, err := fillShifts(ctx)
	if err != nil {
		return nil, err
	}

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil {
		return nil, status.Errorf(codes.Unauthenticated, "login required")
	}
	owners, err := cleanOwners(usr.Email, ctx.Request.FormValue("Owners"))
	if err != nil {
		return nil, err
	}

	cfg := rotang.Configuration{
		Config: rotang.Config{
			Name:        ctx.Request.FormValue("Name"),
			Description: ctx.Request.FormValue("Description"),
			Calendar:    ctx.Request.FormValue("Calendar"),
			Owners:      owners,
			Email: rotang.Email{
				Subject: ctx.Request.FormValue("EmailSubjectTemplate"),
				Body:    ctx.Request.FormValue("EmailBodyTemplate"),
			},
			Shifts: rotang.ShiftConfig{
				Shifts:    shifts,
				Generator: ctx.Request.FormValue("generator"),
			},
		},
		Members: members,
	}

	if err := fillIntegers(ctx, &cfg.Config); err != nil {
		return nil, err
	}
	return &cfg, nil

}

func (h *State) updateGET(ctx *router.Context) (*rotang.Configuration, *auth.User, error) {
	if err := ctx.Request.ParseForm(); err != nil {
		return nil, nil, err
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		return nil, nil, status.Errorf(codes.InvalidArgument, "`name` not set")
	}
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		return nil, nil, err
	}

	if len(rotas) != 1 {
		return nil, nil, status.Errorf(codes.OutOfRange, "unexpected number of rotations returned")
	}
	rota := rotas[0]

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil {
		return nil, nil, status.Errorf(codes.Unauthenticated, "login required")
	}

	isOwner := false
	for _, o := range rota.Config.Owners {
		if o == usr.Email {
			isOwner = true
			break
		}
	}

	if !isOwner {
		return nil, nil, status.Errorf(codes.Unauthenticated, "not in the rotation owners")
	}

	return rotas[0], usr, nil
}

// HandleUpdateRota handles rota configuration updates.
func (h *State) HandleUpdateRota(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if ctx.Request.Method == "GET" {
		rota, usr, err := h.updateGET(ctx)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		templates.MustRender(ctx.Context, ctx.Writer, "pages/modifyrota.html", templates.Args{"Rota": rota, "User": usr, "Owners": strings.Join(rota.Config.Owners, ",")})
		return
	}

	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleModifyRota handle GET/POST requests only", http.StatusBadRequest)
		return
	}

	cfg, err := h.handlePOST(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	if err := h.configStore(ctx.Context).UpdateRotaConfig(ctx.Context, cfg); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	http.Redirect(ctx.Writer, ctx.Request, "managerota", http.StatusFound)
}
