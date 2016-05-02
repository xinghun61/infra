// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP server that handles requests to default
// module.
package frontend

import (
	"net/http"
	"strings"

	"github.com/julienschmidt/httprouter"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/discovery"
	"github.com/luci/luci-go/server/middleware"
	"github.com/luci/luci-go/server/prpc"
	"github.com/luci/luci-go/server/templates"
	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"infra/crimson/proto"
)

// templateBundle is used to render HTML templates. It provides a base args
// passed to all templates.
var templateBundle = &templates.Bundle{
	Loader:    templates.FileSystemLoader("templates"),
	DebugMode: appengine.IsDevAppServer(),
	DefaultArgs: func(c context.Context) (templates.Args, error) {
		loginURL, err := auth.LoginURL(c, "/")
		if err != nil {
			return nil, err
		}
		logoutURL, err := auth.LogoutURL(c, "/")
		if err != nil {
			return nil, err
		}
		isAdmin, err := auth.IsMember(c, "administrators")
		if err != nil {
			return nil, err
		}
		return templates.Args{
			"AppVersion":  strings.Split(info.Get(c).VersionID(), ".")[0],
			"IsAnonymous": auth.CurrentIdentity(c) == identity.AnonymousIdentity,
			"IsAdmin":     isAdmin,
			"User":        auth.CurrentUser(c),
			"LoginURL":    loginURL,
			"LogoutURL":   logoutURL,
		}, nil
	},
}

// Auth middleware. Hard fails when user is not authenticated or not admin.
func requireAuthWeb(h middleware.Handler) middleware.Handler {
	return func(
		c context.Context,
		rw http.ResponseWriter,
		r *http.Request,
		p httprouter.Params) {

		if auth.CurrentIdentity(c) == identity.AnonymousIdentity {
			loginURL, err := auth.LoginURL(c, "/")
			if err != nil {
				logging.Errorf(c, "Failed to get login URL")
			}
			logging.Infof(c, "Redirecting to %s", loginURL)
			http.Redirect(rw, r, loginURL, 302)
			return
		}

		isGoogler, err := auth.IsMember(c, "googlers")
		if err != nil {
			rw.WriteHeader(http.StatusInternalServerError)
			logging.Errorf(c, "Failed to get group membership.")
			return
		}
		if isGoogler {
			h(c, rw, r, p)
		} else {
			templates.MustRender(c, rw, "pages/access_denied.html", nil)
		}
	}
}

// TODO(pgervais) Use svcdec instead of this middleware for pRPC authorization.
// This middleware hard fails when user is not authenticated or not admin.
func requireAuthRPC(h middleware.Handler) middleware.Handler {
	return func(
		c context.Context,
		rw http.ResponseWriter,
		r *http.Request,
		p httprouter.Params) {
		identity := auth.CurrentUser(c).Email
		logging.Infof(c, identity)
		isGoogler, err := auth.IsMember(c, "googlers")
		if err != nil {
			rw.WriteHeader(http.StatusInternalServerError)
			logging.Errorf(c, "Failed to get group membership.")
			return
		}

		if isGoogler {
			h(c, rw, r, p)
			return
		}

		rw.WriteHeader(http.StatusForbidden)
		logging.Errorf(c, "request not authorized: not a googler.")
	}
}

// base is the root of the middleware chain.
func base(h middleware.Handler) httprouter.Handle {
	methods := auth.Authenticator{
		&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		server.CookieAuth,
		&server.InboundAppIDAuthMethod{},
	}
	h = auth.Authenticate(h)
	h = auth.Use(h, methods)
	h = templates.WithTemplates(h, templateBundle)
	return gaemiddleware.BaseProd(h)
}

func baseWeb(h middleware.Handler) httprouter.Handle {
	return base(requireAuthWeb(h))
}

func baseRPC(h middleware.Handler) httprouter.Handle {
	return base(requireAuthRPC(h))
}

//// Routes.

func init() {
	router := httprouter.New()
	server.InstallHandlers(router, base)
	router.GET("/", baseWeb(indexPage))

	var api prpc.Server
	crimson.RegisterGreeterServer(&api, &greeterService{})
	discovery.Enable(&api)
	api.InstallHandlers(router, baseRPC)

	http.DefaultServeMux.Handle("/", router)
}

//// Handlers.

func indexPage(
	c context.Context,
	w http.ResponseWriter,
	r *http.Request,
	p httprouter.Params) {

	templates.MustRender(c, w, "pages/index.html", nil)
}
