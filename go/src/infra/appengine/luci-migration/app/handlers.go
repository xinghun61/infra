// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/data/rand/mathrand"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/sync/parallel"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/milo/api/proto"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	"infra/monorail"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/discovery"
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

func cronDiscoverBuilders(c *router.Context) error {
	// Standard cron job timeout is 10min.
	c.Context, _ = context.WithDeadline(c.Context, clock.Now(c.Context).Add(10*time.Minute))

	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err).Reason("could not get RPC transport").Err()
	}
	httpClient := &http.Client{Transport: transport}

	cfg, err := config.Get(c.Context)
	switch {
	case err != nil:
		return err
	case cfg.Milo.Hostname == "":
		return errors.New("invalid config: milo host unspecified")
	case cfg.Monorail.Hostname == "":
		return errors.New("invalid config: monorail host unspecified")
	}

	discoverer := &discovery.Builders{
		RegistrationSemaphore: make(parallel.Semaphore, 10),
		Buildbot: milo.NewBuildbotPRPCClient(&prpc.Client{
			C:    httpClient,
			Host: cfg.Milo.Hostname,
		}),
		Monorail: monorail.NewEndpointsClient(
			httpClient,
			fmt.Sprintf("https://%s/_ah/api/monorail/v1", cfg.Monorail.Hostname),
		),
		MonorailHostname: cfg.Monorail.Hostname,
	}

	return parallel.FanOutIn(func(work chan<- func() error) {
		for _, m := range cfg.Buildbot.Masters {
			m := m
			work <- func() error {
				masterCtx := logging.SetField(c.Context, "master", m.Name)
				if err := discoverer.Discover(masterCtx, m); err != nil {
					logging.WithError(err).Errorf(masterCtx, "could not discover builders")
				}
				return nil
			}
		}
	})
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
	r.GET("/internal/cron/discover-builders", base, errHandler(cronDiscoverBuilders))

	m := base.Extend(
		templates.WithTemplates(prepareTemplates()),
		auth.Authenticate(server.UsersAPIAuthMethod{}),
	)

	r.GET("/", m, indexPage)

	http.DefaultServeMux.Handle("/", r)
}

func errHandler(f func(c *router.Context) error) router.Handler {
	return func(c *router.Context) {
		err := f(c)
		if err != nil {
			logging.Errorf(c.Context, "Internal server error: %s", err.Error())
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		} else {
			c.Writer.Write([]byte("OK"))
		}
	}
}
