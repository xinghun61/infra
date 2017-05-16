// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package migration

import (
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/context"

	"infra/monorail"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/data/rand/mathrand"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/milo/api/proto"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
)

const (
	miloHost           = "luci-milo.appspot.com"
	monorailAPIRootURL = "https://monorail-prod.appspot.com/_ah/api/monorail/v1"
)

//// Routes.

// prepareTemplates configures templates.Bundle used by all UI handlers.
//
// In particular it includes a set of default arguments passed to all templates.
func prepareTemplates() *templates.Bundle {
	return &templates.Bundle{
		Loader:          templates.FileSystemLoader("templates"),
		DebugMode:       info.IsDevAppServer,
		DefaultTemplate: "base",
		DefaultArgs: func(c context.Context) (templates.Args, error) {
			loginURL, err := auth.LoginURL(c, "/")
			if err != nil {
				return nil, err
			}
			logoutURL, err := auth.LogoutURL(c, "/")
			if err != nil {
				return nil, err
			}
			token, err := xsrf.Token(c)
			if err != nil {
				return nil, err
			}
			return templates.Args{
				"AppVersion":  strings.Split(info.VersionID(c), ".")[0],
				"IsAnonymous": auth.CurrentIdentity(c) == identity.AnonymousIdentity,
				"User":        auth.CurrentUser(c),
				"LoginURL":    loginURL,
				"LogoutURL":   logoutURL,
				"XsrfToken":   token,
			}, nil
		},
	}
}

func indexPage(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", nil)
}

func cronDiscoverBuilders(c *router.Context) {
	// Standard cron job timeout is 10min.
	c.Context, _ = context.WithDeadline(c.Context, clock.Now(c.Context).Add(10*time.Minute))

	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		internalServerError(c, errors.Annotate(err).Reason("could not get RPC transport").Err())
		return
	}
	httpClient := &http.Client{Transport: transport}

	d := &builderDiscovery{
		buildbot: milo.NewBuildbotPRPCClient(&prpc.Client{
			C:    httpClient,
			Host: miloHost,
		}),
		monorail: monorail.NewEndpointsClient(httpClient, monorailAPIRootURL),
	}

	err = d.discoverNewBuilders(c.Context)
	if err != nil {
		internalServerError(c, err)
		return
	}

	ok(c)
}

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	base := gaemiddleware.BaseProd()

	// Setup HTTP routes.
	r := router.New()

	gaemiddleware.InstallHandlersWithMiddleware(r, base)
	r.GET("/internal/cron/discover-builders", base, cronDiscoverBuilders)

	m := base.Extend(
		templates.WithTemplates(prepareTemplates()),
		auth.Authenticate(server.UsersAPIAuthMethod{}),
	)

	r.GET("/", m, indexPage)

	http.DefaultServeMux.Handle("/", r)
}

func internalServerError(c *router.Context, err error) {
	logging.Errorf(c.Context, "Internal server error: %s", err.Error())
	http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
}

func ok(c *router.Context) {
	c.Writer.Write([]byte("OK"))
}

func isDevInstance(c context.Context) bool {
	return strings.HasSuffix(info.AppID(c), "-dev")
}
