// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"net/http"
	"time"

	"context"

	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/appengine"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	aeuser "google.golang.org/appengine/user"
)

var mtvTime = func() *time.Location {
	loc, err := time.LoadLocation("America/Los_Angeles")
	if err != nil {
		panic(err)
	}
	return loc
}()

func adminOrOwner(ctx *router.Context, cfg *rotang.Configuration) bool {
	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		return false
	}
	if aeuser.IsAdmin(appengine.NewContext(ctx.Request)) {
		return true
	}
	for _, m := range cfg.Config.Owners {
		if usr.Email == m {
			return true
		}
	}
	return false
}

// listRotations generates a list of rotations owned by current user.
// If the current user is an admin all rotations will be listed.
func (h *State) listRotations(ctx *router.Context) (templates.Args, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, err
	}
	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		return nil, status.Errorf(codes.PermissionDenied, "not logged in")
	}

	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil && status.Code(err) != codes.NotFound {
		return nil, err
	}

	if !aeuser.IsAdmin(appengine.NewContext(ctx.Request)) {
		var permRotas []*rotang.Configuration
		for _, rota := range rotas {
			for _, m := range rota.Config.Owners {
				if usr.Email == m {
					permRotas = append(permRotas, rota)
				}
			}
		}
	}
	return templates.Args{"Rotas": rotas}, nil
}

// modifyRotations generates the configuration and generators list used by the
// rota-create element.
func (h *State) modifyRotation(ctx *router.Context) (templates.Args, error) {
	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		return nil, status.Errorf(codes.InvalidArgument, "`name` not set")
	}
	rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		return nil, err
	}

	if len(rotas) != 1 {
		return nil, status.Errorf(codes.Internal, "unexpected number of rotations returned")
	}
	rota := rotas[0]

	if !adminOrOwner(ctx, rota) {
		return nil, status.Errorf(codes.PermissionDenied, "not in the rotation owners")
	}

	var members []jsonMember
	ms := h.memberStore(ctx.Context)
	for _, rm := range rota.Members {
		m, err := ms.Member(ctx.Context, rm.Email)
		if err != nil {
			return nil, err
		}
		members = append(members, jsonMember{
			Name:  m.Name,
			Email: m.Email,
			TZ:    m.TZ.String(),
		})
	}

	var resBuf bytes.Buffer
	if err := json.NewEncoder(&resBuf).Encode(&jsonRota{
		Cfg:     *rota,
		Members: members,
	}); err != nil {
		return nil, err
	}
	var genBuf bytes.Buffer
	if err := json.NewEncoder(&genBuf).Encode(h.generators.List()); err != nil {
		return nil, err
	}
	return templates.Args{"Rota": rotaName, "Config": rota, "ConfigJSON": resBuf.String(), "Generators": genBuf.String()}, nil
}

// rota authenticates the request and fetches the rotation configuration.
func (h *State) rota(ctx *router.Context) (*rotang.Configuration, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, err
	}

	rotaName := ctx.Request.FormValue("name")
	if rotaName == "" {
		return nil, status.Errorf(codes.InvalidArgument, "no rota provied")
	}
	rota, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rotaName)
	if err != nil {
		return nil, err
	}
	if len(rota) != 1 {
		return nil, status.Errorf(codes.Internal, "expected only one rota to be returned")
	}

	if !adminOrOwner(ctx, rota[0]) {
		return nil, status.Errorf(codes.PermissionDenied, "not rotation owner")
	}
	return rota[0], nil
}

func buildLegacyMap(h *State) map[string]func(ctx *router.Context, file string) (string, error) {
	return map[string]func(ctx *router.Context, file string) (string, error){
		// Trooper files.
		"trooper.js":           h.legacyTrooper,
		"trooper.json":         h.legacyTrooper,
		"current_trooper.json": h.legacyTrooper,
		"current_trooper.txt":  h.legacyTrooper,
		// Sheriff files.
		"sheriff.js":                     h.legacySheriff,
		"sheriff_cros_mtv.js":            h.legacySheriff,
		"sheriff_cros_nonmtv.js":         h.legacySheriff,
		"sheriff_perf.js":                h.legacySheriff,
		"sheriff_cr_cros_gardeners.js":   h.legacySheriff,
		"sheriff_gpu.js":                 h.legacySheriff,
		"sheriff_angle.js":               h.legacySheriff,
		"sheriff_android.js":             h.legacySheriff,
		"sheriff_ios.js":                 h.legacySheriff,
		"sheriff_v8.js":                  h.legacySheriff,
		"sheriff_perfbot.js":             h.legacySheriff,
		"sheriff.json":                   h.legacySheriff,
		"sheriff_cros_mtv.json":          h.legacySheriff,
		"sheriff_cros_nonmtv.json":       h.legacySheriff,
		"sheriff_perf.json":              h.legacySheriff,
		"sheriff_cr_cros_gardeners.json": h.legacySheriff,
		"sheriff_gpu.json":               h.legacySheriff,
		"sheriff_angle.json":             h.legacySheriff,
		"sheriff_android.json":           h.legacySheriff,
		"sheriff_ios.json":               h.legacySheriff,
		"sheriff_v8.json":                h.legacySheriff,
		"sheriff_perfbot.json":           h.legacySheriff,
		// All rotations
		"all_rotations.js": h.legacyAllRotations,
	}
}

// State holds shared state between handlers.
type State struct {
	projectID      func(context.Context) string
	prodENV        string
	calendar       rotang.Calenderer
	legacyCalendar rotang.Calenderer
	generators     *algo.Generators
	backupCred     func(context.Context) (*http.Client, error)
	memberStore    func(context.Context) rotang.MemberStorer
	shiftStore     func(context.Context) rotang.ShiftStorer
	configStore    func(context.Context) rotang.ConfigStorer
	mailAddress    string
	mailSender     rotang.MailSender
	legacyMap      map[string]func(ctx *router.Context, file string) (string, error)
}

// Options contains the options used by the handlers.
type Options struct {
	ProjectID      func(context.Context) string
	ProdENV        string
	Calendar       rotang.Calenderer
	LegacyCalendar rotang.Calenderer
	Generators     *algo.Generators
	MailSender     rotang.MailSender
	MailAddress    string
	BackupCred     func(context.Context) (*http.Client, error)

	MemberStore func(context.Context) rotang.MemberStorer
	ConfigStore func(context.Context) rotang.ConfigStorer
	ShiftStore  func(context.Context) rotang.ShiftStorer
}

// New creates a new handlers State container.
func New(opt *Options) (*State, error) {
	switch {
	case opt == nil:
		return nil, status.Errorf(codes.InvalidArgument, "opt can not be nil")
	case opt.ProdENV == "":
		return nil, status.Errorf(codes.InvalidArgument, "ProdENV must be set")
	case opt.Calendar == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Calendar can not be nil")
	case opt.LegacyCalendar == nil:
		return nil, status.Errorf(codes.InvalidArgument, "LegacyCalendar can not be nil")
	case opt.Generators == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Genarators can not be nil")
	case opt.MemberStore == nil, opt.ShiftStore == nil, opt.ConfigStore == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Store functions can not be nil")
	case opt.BackupCred == nil:
		return nil, status.Errorf(codes.InvalidArgument, "BackupCred can not be nil")
	case opt.ProjectID == nil:
		return nil, status.Errorf(codes.InvalidArgument, "ProjectID can not be nil")
	}
	h := &State{
		prodENV:        opt.ProdENV,
		projectID:      opt.ProjectID,
		calendar:       opt.Calendar,
		legacyCalendar: opt.LegacyCalendar,
		generators:     opt.Generators,
		memberStore:    opt.MemberStore,
		shiftStore:     opt.ShiftStore,
		configStore:    opt.ConfigStore,
		mailSender:     opt.MailSender,
		mailAddress:    opt.MailAddress,
		backupCred:     opt.BackupCred,
	}
	h.legacyMap = buildLegacyMap(h)
	return h, nil
}

// IsProduction is true if the service is running in production.
func (h *State) IsProduction() bool {
	return h.prodENV == "production"
}

// IsStaging is true if the service is running in staging.
func (h *State) IsStaging() bool {
	return h.prodENV == "staging"
}

// IsLocal is true if the service is running in the local dev environment.
func (h *State) IsLocal() bool {
	return h.prodENV == "local"
}
