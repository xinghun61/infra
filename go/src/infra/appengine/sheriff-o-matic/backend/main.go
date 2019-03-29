// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to the backend analyzer module.
package som

import (
	"encoding/json"

	"net/http"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	"infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/handler"
	"infra/appengine/sheriff-o-matic/som/model"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

const (
	prodAppID = "sheriff-o-matic"
)

// base is the root of the middleware chain.
func base() router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
			server.CookieAuth,
		},
	}
	return standard.Base().Extend(a.GetMiddleware()).Extend(withServiceClients)
}

func withServiceClients(ctx *router.Context, next router.Handler) {
	a := analyzer.New(5, 100)
	setServiceClients(ctx, a)
	ctx.Context = handler.WithAnalyzer(ctx.Context, a)
	next(ctx)
}

func getTrees(c context.Context) map[string]*model.BuildBucketTree {
	// TODO: Replace this with a link to the latest revision, once this is checked in.
	b, err := client.GetGitilesCached(c, "https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/appengine/sheriff-o-matic/config/tree-builders.json?format=text")
	if err != nil {
		logging.Errorf(c, "Couldn't load tree config json: %v", err)
		return nil
	}

	cfg := &struct {
		Trees []*model.BuildBucketTree `json:"trees"`
	}{}
	err = json.Unmarshal(b, cfg)
	if err != nil {
		panic(err.Error())
	}
	ret := map[string]*model.BuildBucketTree{}
	for _, tcfg := range cfg.Trees {
		ret[tcfg.TreeName] = tcfg
	}
	return ret
}

func setServiceClients(ctx *router.Context, a *analyzer.Analyzer) {
	a.Trees = getTrees(ctx.Context)
	if info.AppID(ctx.Context) == prodAppID {
		logReader, findIt, miloClient, crBug, _, testResults, bbucket := client.ProdClients(ctx.Context)
		a.StepAnalyzers = step.DefaultStepAnalyzers(logReader, findIt, testResults)
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(testResults, logReader, findIt)
		a.CrBug = crBug
		a.Milo = miloClient
		a.FindIt = findIt
		a.TestResults = testResults
		a.BuildBucket = bbucket
	} else {
		logReader, findIt, miloClient, crBug, _, testResults, bbucket := client.StagingClients(ctx.Context)
		a.StepAnalyzers = step.DefaultStepAnalyzers(logReader, findIt, testResults)
		a.BuildBucketStepAnalyzers = step.DefaultBuildBucketStepAnalyzers(testResults, logReader, findIt)
		a.CrBug = crBug
		a.Milo = miloClient
		a.FindIt = findIt
		a.TestResults = testResults
		a.BuildBucket = bbucket
	}
}

//// Routes.
func init() {
	r := router.New()
	basemw := base()
	standard.InstallHandlers(r)

	r.GET("/_cron/analyze/:tree", basemw, handler.GetAnalyzeHandler)
	r.POST("/_ah/queue/logdiff", basemw, handler.LogdiffWorker)
	r.GET("/_ah/queue/addannotationtrees", basemw, handler.AnnotationTreeWorker)

	http.DefaultServeMux.Handle("/", r)
}
