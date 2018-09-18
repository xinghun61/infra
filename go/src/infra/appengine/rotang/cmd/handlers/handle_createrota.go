// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"fmt"
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
	if cfg.DaysToSchedule, err = strconv.Atoi(ctx.Request.FormValue("ShiftsToSchedule")); err != nil {
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
	if len(ctx.Request.Form["addEmail"]) != len(ctx.Request.Form["addTZ"]) &&
		len(ctx.Request.Form["addEmail"]) != len(ctx.Request.Form["addName"]) {
		return nil, status.Errorf(codes.InvalidArgument, "Email, TimeZone and Name must all have a value")
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
			Email: v,
		})
	}
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
	for i, v := range ctx.Request.Form["addShiftName"] {
		h, err := strconv.Atoi(ctx.Request.Form["addShiftDuration"][i])
		if err != nil {
			return nil, err
		}
		shifts = append(shifts, rotang.Shift{
			Name:     v,
			Duration: time.Duration(h) * time.Hour,
		})
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
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		usr := auth.CurrentUser(ctx.Context)
		if usr == nil {
			http.Error(ctx.Writer, "login required", http.StatusForbidden)
			return
		}
		templates.MustRender(ctx.Context, ctx.Writer, "pages/createrota.html",
			templates.Args{"Members": ms, "User": usr})
		return
	}

	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleCreateRota handles GET and POST requests only", http.StatusBadRequest)
		return
	}

	if err := ctx.Request.ParseForm(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	members, err := fillMembers(ctx, h.memberStore(ctx.Context))
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	shifts, err := fillShifts(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil {
		http.Error(ctx.Writer, "Login required", http.StatusForbidden)
		return
	}
	owners, err := cleanOwners(usr.Email, ctx.Request.FormValue("Owners"))
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
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
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	if err := h.configStore(ctx.Context).CreateRotaConfig(ctx.Context, &cfg); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	fmt.Fprintf(ctx.Writer, "Rotation %q added!", cfg.Config.Name)
}
