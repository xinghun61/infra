// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/milo/api/proto"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/identity"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/monorail"

	"infra/appengine/luci-migration/common"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/discovery"
	"infra/appengine/luci-migration/scheduling"
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
			"durationString": common.DurationString,
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
		return errors.Annotate(err, "could not get RPC transport").Err()
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
		Build    buildbucket.ApiCommonBuildMessage
		Hostname string
	}
	if err := parsePubSubJSON(c.Request.Body, &msg); err != nil {
		return err
	}

	// Create a Buildbucket client.
	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err, "could not get RPC transport").Tag(transient.Tag).Err()
	}
	bb, err := buildbucket.New(&http.Client{Transport: transport})
	if err != nil {
		return errors.Annotate(err, "could not create buildbucket service").Tag(transient.Tag).Err()
	}
	bb.BasePath = fmt.Sprintf("https://%s/api/buildbucket/v1/", msg.Hostname)

	return scheduling.HandleNotification(c.Context, &msg.Build, bb)
}

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	base := standard.Base()

	// Setup HTTP routes.
	r := router.New()

	standard.InstallHandlers(r)
	r.GET("/internal/cron/discover-builders", base, errHandler(cronDiscoverBuilders))
	r.POST("/_ah/push-handlers/buildbucket", base, taskHandler(handleBuildbucketPubSub))
	r.GET("/internal/cron/analyze-builders", base, errHandler(cronAnalyzeBuilders))
	r.POST("/internal/task/analyze-builder/*ignored", base, taskHandler(handleAnalyzeBuilder))

	m := base.Extend(
		templates.WithTemplates(prepareTemplates()),
		auth.Authenticate(server.UsersAPIAuthMethod{}),
		checkAccess,
	)
	// All POST forms must be protected with XSRF token.
	mxsrf := m.Extend(xsrf.WithTokenCheck)

	r.GET("/", m, errHandler(handleIndexPage))
	r.GET("/masters/:master/", m, errHandler(handleMasterPage))
	r.GET("/masters/:master/builders/:builder/", m, errHandler(handleBuilderPage))
	r.POST("/masters/:master/builders/:builder/", mxsrf, errHandler(handleBuilderPagePost))

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
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)

			logging.Errorf(c.Context, "Internal server error: %s", err)
			if err, ok := err.(errors.MultiError); ok {
				for i, e := range err {
					if e != nil {
						logging.Errorf(c.Context, "Error #%d: %s", i, e)
					}
				}
			}
		}
	}
}

// taskHandler responds with HTTP 500 only if the error returned by f is
// transient, suggesting to retry the request.
func taskHandler(f func(c *router.Context) error) router.Handler {
	return func(c *router.Context) {
		switch err := f(c); {
		case transient.Tag.In(err):
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
		return errors.Annotate(err, "could not parse pubsub message").Err()
	}

	if err := json.Unmarshal(req.Message.Data, data); err != nil {
		return errors.Annotate(err, "could not parse pubsub message data").Err()
	}

	return nil
}
