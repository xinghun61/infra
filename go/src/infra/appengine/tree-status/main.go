// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"html/template"
	"net/http"
	"strings"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/analytics"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/appengine"
)

const (
	authGroup = "tree-status-access"
)

var (
	mainPage = template.Must(template.ParseFiles("./index.html"))
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

func base(includeCookie bool) router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		},
	}
	if includeCookie {
		a.Methods = append(a.Methods, server.CookieAuth)
	}
	return standard.Base().Extend(a.GetMiddleware())
}

func indexPage(ctx *router.Context) {
	c, w, r, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	user := auth.CurrentIdentity(c)

	loginURL, err := auth.LoginURL(c, "/")
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	// TODO(zhangtiff): Replace authentication requirement for main page with API
	// endpoints that serve different data based on ACLs.
	if user.Kind() == identity.Anonymous {
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
		} else {
			http.Redirect(w, r, loginURL, http.StatusFound)
		}
		return
	}

	isGoogler, err := auth.IsMember(c, authGroup)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	if !isGoogler {
		errStatus(c, w, http.StatusForbidden,
			"You don't have access to view this service.")
		return
	}

	logoutURL, err := auth.LogoutURL(c, "/")

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xsrf token: %s", err)
	}

	isStaging := true
	if !strings.HasSuffix(info.AppID(c), "-staging") {
		isStaging = false
	}

	data := map[string]interface{}{
		"IsDevAppServer": info.IsDevAppServer(c),
		"IsStaging":      isStaging,
		"XsrfToken":      tok,
		"AnalyticsID":    analytics.ID(c),
		"User":           user.Email(),
		"LogoutUrl":      logoutURL,
		"LoginUrl":       loginURL,
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
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
	r := router.New()
	basemw := base(true)
	standard.InstallHandlers(r)

	rootRouter := router.New()
	rootRouter.GET("/*path", basemw, indexPage)

	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/api/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/internal/", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}

func main() {
	appengine.Main()
}
