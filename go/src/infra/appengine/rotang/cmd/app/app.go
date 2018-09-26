// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package app sets up the AppEngine routing and h.
package app

import (
	"log"
	"net/http"

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
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	gcal "google.golang.org/api/calendar/v3"
)

const (
	selfURL       = "rota-ng-staging.googleplex.com"
	sheriffConfig = "token/sheriff_secret.json"
	sheriffToken  = "token/sheriff_token.json"
)

type appengineMailer struct{}

func (a *appengineMailer) Send(ctx context.Context, msg *mail.Message) error {
	return mail.Send(ctx, msg)
}

func legacyCred(cfg *oauth2.Config, token *oauth2.Token) func(context.Context) (*http.Client, error) {
	return func(ctx context.Context) (*http.Client, error) {
		return cfg.Client(ctx, token), nil
	}
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
	r := router.New()
	standard.InstallHandlers(r)
	middleware := standard.Base()

	tmw := middleware.Extend(templates.WithTemplates(&templates.Bundle{
		Loader: templates.FileSystemLoader("templates"),
	}), auth.Authenticate(server.UsersAPIAuthMethod{}))

	// Sort out the generators.
	gs := algo.New()
	gs.Register(algo.NewLegacy())
	gs.Register(algo.NewFair())
	gs.Register(algo.NewRandomGen())

	opts := handlers.Options{
		URL:        selfURL,
		Calendar:   calendar.New(serviceDefaultCred()),
		Generators: gs,
		MailSender: &appengineMailer{},
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := handlers.New(&opts)
	if err != nil {
		log.Fatal(err)
	}

	r.GET("/", tmw, h.HandleIndex)
	r.GET("/upload", tmw, h.HandleUpload)
	r.GET("/list", tmw, h.HandleList)
	r.GET("/createrota", tmw, h.HandleCreateRota)
	r.GET("/managerota", tmw, h.HandleManageRota)
	r.GET("/modifyrota", tmw, h.HandleUpdateRota)
	r.GET("/importshifts", tmw, h.HandleShiftImport)

	r.POST("/modifyrota", tmw, h.HandleUpdateRota)
	r.POST("/createrota", tmw, h.HandleCreateRota)
	r.POST("/deleterota", tmw, h.HandleDeleteRota)
	r.POST("/upload", tmw, h.HandleUpload)

	http.DefaultServeMux.Handle("/", r)
}
