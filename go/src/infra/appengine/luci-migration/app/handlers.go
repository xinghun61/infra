// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package app

import (
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
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
	"infra/appengine/luci-migration/flakiness"
)

const accessGroup = "luci-migration-access"

var errNotFound = errors.New("not found")

//// Routes.

// prepareTemplates configures templates.Bundle used by all UI handlers.
//
// In particular it includes a set of default arguments passed to all templates.
func prepareTemplates() *templates.Bundle {
	return &templates.Bundle{
		Loader:          templates.FileSystemLoader("templates"),
		DebugMode:       info.IsDevAppServer,
		DefaultTemplate: "base",
		FuncMap: template.FuncMap{
			"percent": func(v float64) interface{} {
				return int(100 * v)
			},
		},
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
	case cfg.BuildbotServiceHostname == "":
		return errors.New("invalid config: discovery: milo host unspecified")
	case cfg.MonorailHostname == "":
		return errors.New("invalid config: discovery: monorail host unspecified")
	}

	discoverer := &discovery.Builders{
		RegistrationSemaphore: make(parallel.Semaphore, 10),
		Buildbot: milo.NewBuildbotPRPCClient(&prpc.Client{
			C:    httpClient,
			Host: cfg.BuildbotServiceHostname,
		}),
		Monorail: monorail.NewEndpointsClient(
			httpClient,
			fmt.Sprintf("https://%s/_ah/api/monorail/v1", cfg.MonorailHostname),
		),
		MonorailHostname: cfg.MonorailHostname,
	}

	return parallel.FanOutIn(func(work chan<- func() error) {
		for _, m := range cfg.GetMasters() {
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

func handleBuildbucketPubSub(c *router.Context) error {
	var msg struct {
		Build    flakiness.Build
		Hostname string
	}
	if err := parsePubSubJSON(c.Request.Body, &msg); err != nil {
		return err
	}

	// Create a Buildbucket client.
	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err).Reason("could not get RPC transport").Transient().Err()
	}
	bb, err := buildbucket.New(&http.Client{Transport: transport})
	if err != nil {
		return errors.Annotate(err).Reason("could not create buildbucket service").Transient().Err()
	}
	bb.BasePath = fmt.Sprintf("https://%s/api/buildbucket/v1/", msg.Hostname)

	return flakiness.HandleNotification(c.Context, &msg.Build, bb)
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
	r.POST("/_ah/push-handlers/buildbucket", base, taskHandler(handleBuildbucketPubSub))
	r.GET("/internal/cron/analyze-builders", base, errHandler(cronAnalyzeBuilders))
	r.POST("/internal/task/analyze-builder/*ignored", base, taskHandler(handleAnalyzeBuilder))

	m := base.Extend(
		templates.WithTemplates(prepareTemplates()),
		auth.Authenticate(server.UsersAPIAuthMethod{}),
		checkAccess,
	)

	r.GET("/", m, errHandler(handleIndexPage))
	r.GET("/masters/:master/", m, errHandler(handleMasterPage))
	r.GET("/masters/:master/builders/:builder/", m, errHandler(handleBuilderPage))

	http.DefaultServeMux.Handle("/", r)
}

// checkAccess restricts all requests to publicAccessGroup group.
func checkAccess(c *router.Context, next router.Handler) {
	switch allow, err := auth.IsMember(c.Context, accessGroup); {
	case err != nil:
		logging.WithError(err).Errorf(c.Context, "cannot check %q membership", accessGroup)
		http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)

	case allow:
		next(c)

	case auth.CurrentIdentity(c.Context) == identity.AnonymousIdentity:
		loginURL, err := auth.LoginURL(c.Context, c.Request.URL.String())
		if err != nil {
			logging.WithError(err).Errorf(c.Context, "cannot get LoginURL")
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		} else {
			http.Redirect(c.Writer, c.Request, loginURL, http.StatusFound)
		}

	default:
		http.Error(c.Writer, "Access denied", http.StatusForbidden)
	}
}

func errHandler(f func(c *router.Context) error) router.Handler {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			logging.Errorf(c.Context, "Internal server error: %s", err.Error())
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

// taskHandler responds with HTTP 500 only if the error returned by f is
// transient, suggesting to retry the request.
func taskHandler(f func(c *router.Context) error) router.Handler {
	return func(c *router.Context) {
		switch err := f(c); {
		case errors.IsTransient(err):
			logging.WithError(err).Errorf(c.Context, "transient error")
			http.Error(c.Writer, "Please retry", http.StatusInternalServerError)

		case err != nil:
			logging.WithError(err).Errorf(c.Context, "fatal error")
			c.Writer.Write([]byte("Not really OK, but do not retry"))
		}
	}
}

// parsePubSubJSON parses the PubSub message data property as JSON from r into
// data.
func parsePubSubJSON(r io.Reader, data interface{}) error {
	var req struct {
		Message struct {
			Data []byte // base64 on the wire
		}
	}
	if err := json.NewDecoder(r).Decode(&req); err != nil {
		return errors.Annotate(err).Reason("could not parse pubsub message").Err()
	}

	if err := json.Unmarshal(req.Message.Data, data); err != nil {
		return errors.Annotate(err).Reason("could not parse pubsub message data").Err()
	}

	return nil
}
