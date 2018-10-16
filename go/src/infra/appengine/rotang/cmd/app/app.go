// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package app sets up the AppEngine routing and h.
package app

import (
	"io/ioutil"
	"log"
	"net/http"
	"os"

	"infra/appengine/rotang"
	"infra/appengine/rotang/cmd/handlers"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/calendar"
	"infra/appengine/rotang/pkg/datastore"

	"golang.org/x/net/context"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"

	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	gcal "google.golang.org/api/calendar/v3"
)

const (
	authGroup     = "sheriff-o-matic-access"
	selfURL       = "rota-ng-staging.googleplex.com"
	sheriffConfig = "token/sheriff_secret.json"
	sheriffToken  = "token/sheriff_token.json"
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

func requireGoogler(c *router.Context, next router.Handler) {
	isGoogler, err := auth.IsMember(c.Context, authGroup)
	switch {
	case err != nil:
		errStatus(c.Context, c.Writer, http.StatusInternalServerError, err.Error())
	case !isGoogler:
		errStatus(c.Context, c.Writer, http.StatusForbidden, "Access denied")
	default:
		next(c)
	}
}

func legacyCred() (func(context.Context) (*http.Client, error), error) {
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

	return func(ctx context.Context) (*http.Client, error) {
		return config.Client(ctx, &oauth2.Token{
			RefreshToken: string(t),
			TokenType:    "Bearer",
		}), nil
	}, nil
}

func serviceDefaultCred() func(context.Context) (*http.Client, error) {
	return func(ctx context.Context) (*http.Client, error) {
		return google.DefaultClient(ctx, gcal.CalendarScope)
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

	lcred, err := legacyCred()
	if err != nil {
		log.Fatal(err)
	}
	cred := serviceDefaultCred()
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

	opts := handlers.Options{
		URL:            selfURL,
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
	r.GET("/createrota", protected, h.HandleCreateRota)
	r.GET("/managerota", protected, h.HandleManageRota)
	r.GET("/modifyrota", protected, h.HandleUpdateRota)
	r.GET("/importshifts", protected, h.HandleShiftImport)
	r.GET("/manageshifts", protected, h.HandleManageShifts)
	r.GET("/legacy/:name", tmw, h.HandleLegacy)

	r.POST("/shiftsupdate", protected, h.HandleShiftUpdate)
	r.POST("/shiftsgenerate", protected, h.HandleShiftGenerate)
	r.POST("/generate", protected, h.HandleGenerate)
	r.POST("/modifyrota", protected, h.HandleUpdateRota)
	r.POST("/createrota", protected, h.HandleCreateRota)
	r.POST("/deleterota", protected, h.HandleDeleteRota)
	r.POST("/upload", protected, h.HandleUpload)

	// Recurring jobs.
	r.GET("/cron/joblegacy", tmw, h.JobLegacy)

	http.DefaultServeMux.Handle("/", r)
}
