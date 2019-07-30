// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"strings"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	"infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/handler"
	"infra/monorail"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/portal"
	"go.chromium.org/luci/server/router"
)

const (
	authGroup             = "sheriff-o-matic-access"
	settingsKey           = "tree"
	productionAnalyticsID = "UA-55762617-1"
	stagingAnalyticsID    = "UA-55762617-22"
	prodAppID             = "sheriff-o-matic"
)

var (
	mainPage         = template.Must(template.ParseFiles("./index.html"))
	accessDeniedPage = template.Must(template.ParseFiles("./access-denied.html"))
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

func indexPage(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	if p.ByName("path") == "" {
		http.Redirect(w, r, "/chromium", http.StatusFound)
		return
	}

	user := auth.CurrentIdentity(c)

	if user.Kind() == identity.Anonymous {
		url, err := auth.LoginURL(c, p.ByName("path"))
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf(
				"You must login. Additionally, an error was encountered while serving this request: %s", err.Error()))
		} else {
			http.Redirect(w, r, url, http.StatusFound)
		}

		return
	}

	isGoogler, err := auth.IsMember(c, authGroup)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logoutURL, err := auth.LogoutURL(c, "/")

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	if !isGoogler {
		err = accessDeniedPage.Execute(w, map[string]interface{}{
			"Group":     authGroup,
			"LogoutURL": logoutURL,
		})
		if err != nil {
			logging.Errorf(c, "while rendering index: %s", err)
		}
		return
	}

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xsrf token: %s", err)
	}

	AnalyticsID := stagingAnalyticsID
	isStaging := true
	if !strings.HasSuffix(info.AppID(c), "-staging") {
		logging.Debugf(c, "Using production GA ID for app %s", info.AppID(c))
		AnalyticsID = productionAnalyticsID
		isStaging = false
	}

	trees, err := handler.GetTrees(c)
	if err != nil {
		logging.Errorf(c, "while getting trees: %s", err)
	}

	data := map[string]interface{}{
		"User":           user.Email(),
		"LogoutUrl":      logoutURL,
		"IsDevAppServer": info.IsDevAppServer(c),
		"IsStaging":      isStaging,
		"XsrfToken":      tok,
		"AnalyticsID":    AnalyticsID,
		"Trees":          string(trees),
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

// base is the root of the middleware chain.
func base(includeCookie bool) router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
		},
	}
	if includeCookie {
		a.Methods = append(a.Methods, server.CookieAuth)
	}
	return standard.Base().Extend(a.GetMiddleware()).Extend(withServiceClients)
}

func withServiceClients(ctx *router.Context, next router.Handler) {
	a := analyzer.New(5, 100)
	setServiceClients(ctx, a)
	ctx.Context = handler.WithAnalyzer(ctx.Context, a)
	next(ctx)
}

func setServiceClients(ctx *router.Context, a *analyzer.Analyzer) {
	// TODO: audit this code to make sure frontend module actually uses
	// Analyzer and/or any of these clients besides milo and crbug.
	if info.AppID(ctx.Context) == prodAppID {
		logReader, findIt, miloClient, crBug, _, testResults, _ := client.ProdClients(ctx.Context)
		a.StepAnalyzers = step.DefaultStepAnalyzers(logReader, findIt, testResults)
		a.CrBug = crBug
		a.Milo = miloClient
		a.FindIt = findIt
	} else {
		logReader, findIt, miloClient, crBug, _, testResults, _ := client.StagingClients(ctx.Context)
		a.StepAnalyzers = step.DefaultStepAnalyzers(logReader, findIt, testResults)
		a.CrBug = crBug
		a.Milo = miloClient
		a.FindIt = findIt
	}
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

func noopHandler(ctx *router.Context) {
	return
}

func getXSRFToken(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xsrf token: %s", err)
	}

	data := map[string]string{
		"token": tok,
	}
	txt, err := json.Marshal(data)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(txt)
}

func newBugQueueHandler(c context.Context) *handler.BugQueueHandler {
	var monorailClient monorail.MonorailClient
	if info.AppID(c) == prodAppID {
		monorailClient = client.NewMonorail(c, "https://monorail-prod.appspot.com")
	} else {
		monorailClient = client.NewMonorail(c, "https://monorail-staging.appspot.com")
	}
	bqh := &handler.BugQueueHandler{
		Monorail: monorailClient,
	}
	return bqh
}

func refreshBugQueueHandler(ctx *router.Context) {
	bqh := newBugQueueHandler(ctx.Context)
	bqh.RefreshBugQueueHandler(ctx)
}

func getBugQueueHandler(ctx *router.Context) {
	bqh := newBugQueueHandler(ctx.Context)
	bqh.GetBugQueueHandler(ctx)
}

func getUncachedBugsHandler(ctx *router.Context) {
	bqh := newBugQueueHandler(ctx.Context)
	bqh.GetUncachedBugsHandler(ctx)
}

func newAnnotationHandler(c context.Context) *handler.AnnotationHandler {
	bqh := newBugQueueHandler(c)
	return &handler.AnnotationHandler{
		Bqh: bqh,
	}
}

func refreshAnnotationsHandler(ctx *router.Context) {
	ah := newAnnotationHandler(ctx.Context)
	ah.RefreshAnnotationsHandler(ctx)
}

func getAnnotationsHandler(ctx *router.Context) {
	ah := newAnnotationHandler(ctx.Context)
	activeKeys := map[string]interface{}{}
	activeAlerts := handler.GetAlerts(ctx, true, false)
	for _, alrt := range activeAlerts.Alerts {
		activeKeys[alrt.Key] = nil
	}
	ah.GetAnnotationsHandler(ctx, activeKeys)
}

func postAnnotationsHandler(ctx *router.Context) {
	ah := newAnnotationHandler(ctx.Context)
	ah.PostAnnotationsHandler(ctx)
}

//// Routes.
func init() {

	portal.RegisterPage(settingsKey, handler.SettingsPage{})

	r := router.New()
	basemw := base(true)

	protected := basemw.Extend(requireGoogler)

	standard.InstallHandlers(r)
	r.GET("/api/v1/alerts/:tree", protected, handler.GetAlertsHandler)
	r.GET("/api/v1/unresolved/:tree", protected, handler.GetUnresolvedAlertsHandler)
	r.GET("/api/v1/resolved/:tree", protected, handler.GetResolvedAlertsHandler)
	r.GET("/api/v1/restarts/:tree", protected, handler.GetRestartingMastersHandler)
	r.GET("/api/v1/xsrf_token", protected, getXSRFToken)

	// Disallow cookies because this handler should not be accessible by regular
	// users.
	r.POST("/api/v1/alerts/:tree", base(false).Extend(requireGoogler), handler.PostAlertsHandler)
	r.POST("/api/v1/alert/:tree/:key", base(false).Extend(requireGoogler), handler.PostAlertHandler)
	r.POST("/api/v1/resolve/:tree", protected, handler.ResolveAlertHandler)

	r.GET("/api/v1/annotations/:tree", protected, getAnnotationsHandler)
	r.POST("/api/v1/annotations/:tree/:action", protected, postAnnotationsHandler)
	r.POST("/api/v1/filebug/", protected, handler.FileBugHandler)
	r.GET("/api/v1/bugqueue/:label", protected, getBugQueueHandler)
	r.GET("/api/v1/bugqueue/:label/uncached/", protected, getUncachedBugsHandler)
	r.GET("/api/v1/revrange/:host/:repo", basemw, handler.GetRevRangeHandler)
	r.GET("/api/v1/testexpectations", protected, handler.GetLayoutTestsHandler)
	r.POST("/api/v1/testexpectation", protected, handler.PostLayoutTestExpectationChangeHandler)
	r.GET("/logos/:tree", protected, handler.GetTreeLogoHandler)
	r.GET("/_/autocomplete/:query", protected, handler.GetUserAutocompleteHandler)

	// Non-public endpoints.
	r.GET("/_cron/refresh/bugqueue/:label", basemw, refreshBugQueueHandler)
	r.GET("/_cron/annotations/flush_old/", basemw, handler.FlushOldAnnotationsHandler)
	r.GET("/_cron/annotations/refresh/", basemw, refreshAnnotationsHandler)
	r.POST("/_/clientmon", basemw, handler.PostClientMonHandler)

	// Ingore reqeuests from builder-alerts rather than 404.
	r.GET("/alerts", standard.Base(), noopHandler)
	r.POST("/alerts", standard.Base(), noopHandler)

	rootRouter := router.New()
	rootRouter.GET("/*path", basemw, indexPage)

	http.DefaultServeMux.Handle("/_cron/", r)
	http.DefaultServeMux.Handle("/api/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/internal/", r)
	http.DefaultServeMux.Handle("/_/", r)
	http.DefaultServeMux.Handle("/logos/", r)
	http.DefaultServeMux.Handle("/alerts", r)
	http.DefaultServeMux.Handle("/alertdiff/", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}
