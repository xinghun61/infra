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

	"infra/appengine/sheriff-o-matic/som"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/settings"
)

const (
	authGroup             = "sheriff-o-matic-access"
	settingsKey           = "tree"
	productionAnalyticsID = "UA-55762617-1"
	stagingAnalyticsID    = "UA-55762617-22"
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

	trees, err := som.GetTrees(c)
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
	return gaemiddleware.BaseProd().Extend(a.GetMiddleware())
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

//// Routes.
func init() {

	settings.RegisterUIPage(settingsKey, som.SettingsUIPage{})

	r := router.New()
	basemw := base(true)

	protected := basemw.Extend(requireGoogler)

	gaemiddleware.InstallHandlers(r)
	r.GET("/api/v1/alerts/:tree", protected, som.GetAlertsHandler)
	r.GET("/api/v1/restarts/:tree", protected, som.GetRestartingMastersHandler)
	r.GET("/api/v1/xsrf_token", protected, getXSRFToken)

	// Disallow cookies because this handler should not be accessible by regular
	// users.
	r.POST("/api/v1/alerts/:tree", base(false).Extend(requireGoogler), som.PostAlertsHandler)
	r.POST("/api/v1/alert/:tree/:key", base(false).Extend(requireGoogler), som.PostAlertHandler)
	r.POST("/api/v1/resolve/:tree", protected, som.ResolveAlertHandler)
	r.GET("/api/v1/annotations/", protected, som.GetAnnotationsHandler)
	r.POST("/api/v1/annotations/:annKey/:action", protected, som.PostAnnotationsHandler)
	r.GET("/api/v1/bugqueue/:label", protected, som.GetBugQueueHandler)
	r.GET("/api/v1/bugqueue/:label/uncached/", protected, som.GetUncachedBugsHandler)
	r.GET("/api/v1/revrange/:start/:end", basemw, som.GetRevRangeHandler)
	r.GET("/api/v1/testexpectations", protected, som.GetLayoutTestsHandler)
	r.POST("/api/v1/testexpectation", protected, som.PostLayoutExpectationHandler)
	r.GET("/logos/:tree", protected, som.GetTreeLogoHandler)
	r.GET("/alertdiff/:tree", protected, som.GetMiloDiffHandler)
	r.GET("/api/v1/logdiff/:tree", protected, som.LogDiffHandler)
	r.GET("/logdiff/:tree", protected, som.GetLogDiffHandler)

	// Non-public endpoints.
	r.GET("/_cron/refresh/bugqueue/:label", basemw, som.RefreshBugQueueHandler)
	r.GET("/_cron/annotations/flush_old/", basemw, som.FlushOldAnnotationsHandler)
	r.GET("/_cron/annotations/refresh/", basemw, som.RefreshAnnotationsHandler)
	r.POST("/_/clientmon", basemw, som.PostClientMonHandler)

	// Ingore reqeuests from builder-alerts rather than 404.
	r.GET("/alerts", gaemiddleware.BaseProd(), noopHandler)
	r.POST("/alerts", gaemiddleware.BaseProd(), noopHandler)

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
	http.DefaultServeMux.Handle("/logdiff/", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}
