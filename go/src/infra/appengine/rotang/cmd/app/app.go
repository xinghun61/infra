// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package app sets up the AppEngine routing and h.
package app

import (
	"context"
	"io/ioutil"
	"log"
	"net/http"
	"os"

	"infra/appengine/rotang"
	"infra/appengine/rotang/cmd/handlers"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/calendar"
	"infra/appengine/rotang/pkg/datastore"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"

	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/appengine"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	gcal "google.golang.org/api/calendar/v3"
)

const (
	datastoreScope = "https://www.googleapis.com/auth/datastore"
	authGroup      = "sheriff-o-matic-access"
	sheriffConfig  = "token/sheriff_secret.json"
	sheriffToken   = "token/sheriff_token.json"
)

type appengineMailer struct{}

func (a *appengineMailer) Send(ctx context.Context, msg *mail.Message) error {
	return mail.Send(ctx, msg)
}

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

func requireGoogler(ctx *router.Context, next router.Handler) {
	isGoogler, err := auth.IsMember(ctx.Context, authGroup)
	switch {
	case err != nil:
		errStatus(ctx.Context, ctx.Writer, http.StatusInternalServerError, err.Error())
	case !isGoogler:
		url, err := auth.LoginURL(ctx.Context, ctx.Params.ByName("path"))
		if err != nil {
			errStatus(ctx.Context, ctx.Writer, http.StatusForbidden, "Access denied err:"+err.Error())
			return
		}
		http.Redirect(ctx.Writer, ctx.Request, url, http.StatusFound)
		return
	default:
		next(ctx)
	}
}

const legacyTokenID = "LegacyToken"

func dsLegacyCred(ts func(context.Context) rotang.TokenStorer) func(*router.Context) (*http.Client, error) {
	return func(ctx *router.Context) (*http.Client, error) {
		clt, err := ts(ctx.Context).Client(ctx, legacyTokenID)
		if err != nil {
			if status.Code(err) != codes.NotFound {
				return nil, err
			}
			logging.Warningf(ctx.Context, "token: %q not found in datastore, trying to fetch from token files")
			b, err := ioutil.ReadFile(sheriffConfig)
			if err != nil {
				return nil, err
			}
			config, err := google.ConfigFromJSON(b, gcal.CalendarScope)
			if err != nil {
				return nil, err
			}

			t, err := ioutil.ReadFile(sheriffToken)
			if err != nil {
				return nil, err
			}
			token := &oauth2.Token{
				RefreshToken: string(t),
				TokenType:    "Bearer",
			}
			if err := ts(ctx.Context).CreateToken(ctx.Context, legacyTokenID, string(b), token); err != nil {
				return nil, err
			}
			clt = config.Client(appengine.NewContext(ctx.Request), token)
		}
		return clt, nil
	}
}

func serviceDefaultCred(scope string) func(*router.Context) (*http.Client, error) {
	return func(ctx *router.Context) (*http.Client, error) {
		return google.DefaultClient(appengine.NewContext(ctx.Request), scope)
	}
}

func setupStoreHandlers(o *handlers.Options, sf func(context.Context) *datastore.Store) {
	o.MemberStore = func(ctx context.Context) rotang.MemberStorer {
		return sf(ctx)
	}
	o.ShiftStore = func(ctx context.Context) rotang.ShiftStorer {
		return sf(ctx)
	}
	o.ConfigStore = func(ctx context.Context) rotang.ConfigStorer {
		return sf(ctx)
	}
}

func init() {
	prodENV := os.Getenv("PROD_ENV")
	switch prodENV {
	case "production", "local", "staging":
	default:
		log.Fatal("env PROD_ENV must be set to one of `production`, `local` or `staging`")
	}

	lcred := dsLegacyCred(func(ctx context.Context) rotang.TokenStorer {
		return datastore.New(ctx)
	})

	cred := serviceDefaultCred(gcal.CalendarScope)
	if prodENV == "local" {
		cred = lcred
	}

	r := router.New()
	standard.InstallHandlers(r)
	middleware := standard.Base()

	tmw := middleware.Extend(templates.WithTemplates(&templates.Bundle{
		Loader: templates.FileSystemLoader("templates"),
	}), auth.Authenticate(server.UsersAPIAuthMethod{}))

	protected := tmw.Extend(requireGoogler)

	// Sort out the generators.
	gs := algo.New()
	gs.Register(algo.NewLegacy())
	gs.Register(algo.NewFair())
	gs.Register(algo.NewRandomGen())
	gs.Register(algo.NewTZFair())

	// And the modifiers.
	gs.RegisterModifier(algo.NewWeekendSkip())
	gs.RegisterModifier(algo.NewSplitShift())

	opts := handlers.Options{
		ProjectID:      appengine.AppID,
		BackupCred:     serviceDefaultCred(datastoreScope),
		LegacyCalendar: calendar.New(lcred),
		Calendar:       calendar.New(cred),
		Generators:     gs,
		MailSender:     &appengineMailer{},
		ProdENV:        prodENV,
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := handlers.New(&opts)
	if err != nil {
		log.Fatal(err)
	}

	r.GET("/", protected, h.HandleIndex)
	r.GET("/upload", protected, h.HandleUpload)
	r.GET("/list", protected, h.HandleList)
	r.GET("/createrota", protected, h.HandleRotaCreate)
	r.GET("/managerota", protected, h.HandleManageRota)
	r.GET("/modifyrota", protected, h.HandleRotaModify)
	r.GET("/importshiftsjson", protected, h.HandleShiftImportJSON)
	r.GET("/manageshifts", protected, h.HandleManageShifts)
	r.GET("/legacy/:name", tmw, h.HandleLegacy)
	r.GET("/oncall", protected, h.HandleOncall)
	r.GET("/oncall/:name", protected, h.HandleOncall)
	r.GET("/memberjson", protected, h.HandleMember)
	r.GET("/switchlist", protected, h.HandleRotaSwitchList)
	r.GET("/switchrota", protected, h.HandleRotaSwitch)
	r.GET("/caltest", protected, h.HandleCalTest)
	r.GET("/emailtest", protected, h.HandleEmailTest)
	r.GET("/emailjsontest", protected, h.HandleEmailTestJSON)
	r.GET("/emailsendtest", protected, h.HandleEmailTestSend)

	r.POST("/oncalljson", protected, h.HandleOncallJSON)
	r.POST("/shiftsupdate", protected, h.HandleShiftUpdate)
	r.POST("/shiftsgenerate", protected, h.HandleShiftGenerate)
	r.POST("/shiftswap", protected, h.HandleShiftSwap)
	r.POST("/generate", protected, h.HandleGenerate)
	r.POST("/modifyrota", protected, h.HandleRotaModify)
	r.POST("/createrota", protected, h.HandleRotaCreate)
	r.POST("/deleterota", protected, h.HandleDeleteRota)
	r.POST("/upload", protected, h.HandleUpload)
	r.POST("/enabledisable", protected, h.HandleEnableDisable)
	r.POST("/memberjson", protected, h.HandleMember)

	// Recurring jobs.
	r.GET("/cron/joblegacy", tmw, h.JobLegacy)
	r.GET("/cron/backup", tmw, h.JobBackup)
	r.GET("/cron/email", tmw, h.JobEmail)
	r.GET("/cron/schedule", tmw, h.JobSchedule)
	r.GET("/cron/eventupdate", tmw, h.JobEventUpdate)

	http.DefaultServeMux.Handle("/", r)
}
