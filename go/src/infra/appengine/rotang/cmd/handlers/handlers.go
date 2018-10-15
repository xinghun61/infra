// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"time"

	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"golang.org/x/oauth2"
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

func buildLegacyMap(h *State) map[string]func(ctx *router.Context, file string) (string, error) {
	return map[string]func(ctx *router.Context, file string) (string, error){
		// Trooper files.
		"trooper.js":           h.legacyTrooper,
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
	}
}

// State holds shared state between handlers.
type State struct {
	selfURL        string
	prodENV        string
	calendar       rotang.Calenderer
	legacyCalendar rotang.Calenderer
	generators     *algo.Generators
	memberStore    func(context.Context) rotang.MemberStorer
	oauthConfig    *oauth2.Config
	token          *oauth2.Token
	shiftStore     func(context.Context) rotang.ShiftStorer
	configStore    func(context.Context) rotang.ConfigStorer
	mailAddress    string
	mailSender     rotang.MailSender
	legacyMap      map[string]func(ctx *router.Context, file string) (string, error)
}

// Options contains the options used by the handlers.
type Options struct {
	URL            string
	ProdENV        string
	Calendar       rotang.Calenderer
	LegacyCalendar rotang.Calenderer
	Generators     *algo.Generators
	MailSender     rotang.MailSender
	MailAddress    string

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
	case opt.URL == "":
		return nil, status.Errorf(codes.InvalidArgument, "URL must be set")
	case opt.Calendar == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Calendar can not be nil")
	case opt.LegacyCalendar == nil:
		return nil, status.Errorf(codes.InvalidArgument, "LegacyCalendar can not be nil")
	case opt.Generators == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Genarators can not be nil")
	case opt.MemberStore == nil, opt.ShiftStore == nil, opt.ConfigStore == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Store functions can not be nil")
	}
	h := &State{
		prodENV:        opt.ProdENV,
		selfURL:        opt.URL,
		calendar:       opt.Calendar,
		legacyCalendar: opt.LegacyCalendar,
		generators:     opt.Generators,
		memberStore:    opt.MemberStore,
		shiftStore:     opt.ShiftStore,
		configStore:    opt.ConfigStore,
		mailSender:     opt.MailSender,
		mailAddress:    opt.MailAddress,
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
