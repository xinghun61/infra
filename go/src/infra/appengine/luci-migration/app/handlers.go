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

package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"strings"
	"time"

	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/bugs"
	"infra/appengine/luci-migration/common"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/discovery"
	"infra/appengine/luci-migration/scheduling"
	"infra/appengine/luci-migration/storage"
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
		DefaultArgs: func(c context.Context, e *templates.Extra) (templates.Args, error) {
			loginURL, err := auth.LoginURL(c, e.Request.URL.RequestURI())
			if err != nil {
				return nil, err
			}
			logoutURL, err := auth.LogoutURL(c, e.Request.URL.RequestURI())
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

func cronUpdateBugDescriptions(c *router.Context) error {
	// Standard cron job timeout is 10min.
	c.Context, _ = context.WithDeadline(c.Context, clock.Now(c.Context).Add(10*time.Minute))
	deadline, _ := c.Context.Deadline()

	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err, "could not get RPC transport").Err()
	}
	monorail := bugs.DefaultFactory(transport)

	// Note: in practice, this code needs to run a constant number of times
	// so don't bother with concurrency of two queries.
	var toUpdate []*storage.Builder
	q := datastore.NewQuery(storage.BuilderKind).
		Lt("IssueDescriptionVersion", bugs.DescriptionVersion).
		KeysOnly(true)
	err = datastore.GetAll(c.Context, q, &toUpdate)
	if err != nil {
		return err
	}

	logging.Infof(c.Context, "%d bugs to update", len(toUpdate))
	if len(toUpdate) == 0 {
		return nil
	}

	return parallel.WorkPool(10, func(work chan<- func() error) {
		for _, builder := range toUpdate {
			builder := builder
			work <- func() error {
				return datastore.RunInTransaction(c.Context, func(c context.Context) error {
					if deadline.Sub(clock.Now(c)) < time.Minute {
						return fmt.Errorf("not enough time")
					}
					err := datastore.Get(c, builder)
					if err != nil {
						return errors.Annotate(err, "could not get builder %q", &builder.ID).Err()
					}
					if builder.IssueDescriptionVersion >= bugs.DescriptionVersion {
						return nil
					}
					err = bugs.UpdateBuilderBugDescription(c, monorail, builder)
					if err != nil {
						return err
					}
					return datastore.Put(c, builder)
				}, nil)
			}
		}
	})
}

func cronDiscoverBuilders(c *router.Context) error {
	// Standard cron job timeout is 10min.
	c.Context, _ = context.WithDeadline(c.Context, clock.Now(c.Context).Add(10*time.Minute))

	transport, err := auth.GetRPCTransport(c.Context, auth.AsSelf)
	if err != nil {
		return errors.Annotate(err, "could not get RPC transport").Err()
	}

	cfg := config.Get(c.Context)
	switch {
	case cfg.MonorailHostname == "":
		return errors.New("invalid config: discovery: monorail host unspecified")
	}

	discoverer := &discovery.Builders{
		DatastoreOpSem:   make(parallel.Semaphore, 10),
		Monorail:         bugs.DefaultFactory(transport),
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
		Build    buildbucket.LegacyApiCommonBuildMessage
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
	bb.BasePath = fmt.Sprintf("https://%s/_ah/api/buildbucket/v1/", msg.Hostname)

	b, err := scheduling.ParseBuild(&msg.Build)
	if err != nil {
		return err
	}
	handler := &scheduling.Scheduler{Buildbucket: bb}
	return handler.BuildCompleted(c.Context, b)
}

func main() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	mwBase := standard.Base().Extend(config.Middleware)
	r := router.New()

	standard.InstallHandlers(r)
	r.GET("/internal/cron/discover-builders", mwBase, errHandler(cronDiscoverBuilders))
	// TODO: make it an API instead of cron when we have a strong need for API.
	r.GET("/internal/cron/update-bugs", mwBase, errHandler(cronUpdateBugDescriptions))
	r.POST("/_ah/push-handlers/buildbucket", mwBase, taskHandler(handleBuildbucketPubSub))
	r.GET("/internal/cron/analyze-builders", mwBase, errHandler(cronAnalyzeBuilders))
	r.POST("/internal/task/analyze-builder/*ignored", mwBase, taskHandler(handleAnalyzeBuilder))
	r.POST("/internal/task/notify/*ignored", mwBase, taskHandler(handleNotifyOnBuilderChange))

	mwFrontend := mwBase.Extend(
		corsMiddleware,
		templates.WithTemplates(prepareTemplates()),
		auth.Authenticate(
			server.UsersAPIAuthMethod{},
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		),
	)
	mwMasterRoute := mwFrontend.Extend(checkMasterAccess)
	// All POST forms must be protected with XSRF token.

	r.GET("/", mwFrontend, errHandler(handleIndexPage))
	r.GET("/masters/:master/", mwMasterRoute, errHandler(handleMasterPage))
	r.OPTIONS("/masters/:master/", mwMasterRoute, okHandler)
	r.GET("/masters/:master/builders/:builder/", mwMasterRoute, errHandler(handleBuilderPage))
	r.POST("/masters/:master/builders/:builder/", mwMasterRoute.Extend(xsrf.WithTokenCheck), errHandler(handleBuilderPagePost))
	r.OPTIONS("/masters/:master/builders/:builder/", mwMasterRoute, okHandler)
	r.GET("/masters/:master/builders/:builder/changes", mwMasterRoute, errHandler(handleBuilderUpdatesPage))

	http.DefaultServeMux.Handle("/", r)
	appengine.Main()
}

func respondWithJSON(r *http.Request) bool {
	return strings.ToLower(r.FormValue("format")) == "json"
}

func okHandler(c *router.Context) {
	c.Writer.WriteHeader(http.StatusOK)
}

func corsMiddleware(c *router.Context, next router.Handler) {
	defer next(c)

	// Apply it only if JSON response is requested.
	if !respondWithJSON(c.Request) {
		return
	}

	// Allow CORS requests only from Gerrit and localhost.
	const originHeader = "Origin"
	origin := c.Request.Header.Get(originHeader)
	switch {
	case strings.HasPrefix(origin, "http://localhost:"):
	case strings.HasSuffix(origin, ".googlesource.com"):
	default:
		return
	}

	h := c.Writer.Header()
	h.Add("Access-Control-Allow-Origin", origin)
	h.Add("Vary", originHeader)
	h.Add("Access-Control-Allow-Credentials", "true")

	if c.Request.Method == "OPTIONS" {
		h.Add("Access-Control-Allow-Headers", "Origin, Content-Type, Accept, Authorization, User-Agent")
		h.Add("Access-Control-Allow-Methods", "OPTIONS, GET")
		h.Add("Access-Control-Max-Age", "600") // 10min
	}
}

// checkMasterAccess checks access to the master.
func checkMasterAccess(c *router.Context, next router.Handler) {
	master := c.Params.ByName("master")

	var masterCfg *config.Master
	for _, m := range config.Get(c.Context).Masters {
		if m.Name == master {
			masterCfg = m
			break
		}
	}
	switch {
	case masterCfg == nil:
		http.NotFound(c.Writer, c.Request)
		return
	case masterCfg.Public:
		next(c)
		return
	}

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
			Data       []byte // base64 on the wire
			Attributes map[string]interface{}
		}
	}
	if err := json.NewDecoder(r).Decode(&req); err != nil {
		return errors.Annotate(err, "could not parse pubsub message").Err()
	}
	if v, ok := req.Message.Attributes["version"].(string); ok && v != "v1" {
		// Ignore v2 pubsub messages. We read v1.
		return nil
	}
	if err := json.Unmarshal(req.Message.Data, data); err != nil {
		return errors.Annotate(err, "could not parse pubsub message data").Err()
	}

	return nil
}
