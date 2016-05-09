// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP server that handles requests to default
// module.
package frontend

import (
	"net/http"
	"strings"

	"github.com/golang/protobuf/proto"

	"github.com/julienschmidt/httprouter"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/grpcutil"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/discovery"
	"github.com/luci/luci-go/server/middleware"
	"github.com/luci/luci-go/server/prpc"
	"github.com/luci/luci-go/server/templates"
	"golang.org/x/net/context"
	"google.golang.org/appengine"
	"google.golang.org/grpc/codes"

	"infra/crimson/proto"
)

// templateBundle is used to render HTML templates. It provides a base args
// passed to all templates.
var (
	templateBundle = &templates.Bundle{
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
	// People with read/write access to the database (c-i-a group)
	rwGroup = "crimson"
)

// Auth middleware. Hard fails when user is not authorized.
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

		isGoogler, err := auth.IsMember(c, rwGroup)
		if err != nil {
			rw.WriteHeader(http.StatusInternalServerError)
			logging.Errorf(c, "Failed to get group membership.")
			return
		}
		if isGoogler {
			h(c, rw, r, p)
			return
		}

		templates.MustRender(c, rw, "pages/access_denied.html", nil)
	}
}

// checkAuthorizationPrpc is a prelude function in the svcdec sense.
// It hard fails when the user is not authorized.
func checkAuthorizationPrpc(
	c context.Context, methodName string, req proto.Message) (context.Context, error) {

	identity := auth.CurrentIdentity(c)
	logging.Infof(c, "%s", identity)
	hasAccess, err := auth.IsMember(c, rwGroup)
	if err != nil {
		return nil, grpcutil.Errf(codes.Internal, "%s", err)
	}
	if hasAccess {
		return c, nil
	}
	return nil, grpcutil.Errf(codes.PermissionDenied,
		"%s is not allowed to call APIs", auth.CurrentIdentity(c))
}

func base(h middleware.Handler) httprouter.Handle {
	methods := auth.Authenticator{
		server.CookieAuth,
	}
	h = auth.Authenticate(h)
	h = auth.Use(h, methods)
	h = templates.WithTemplates(h, templateBundle)
	return gaemiddleware.BaseProd(h)
}

// webBase sets up authentication/authorization for http requests.
func webBase(h middleware.Handler) httprouter.Handle {
	return base(requireAuthWeb(h))
}

// prpcBase is the middleware for pRPC API handlers.
func prpcBase(h middleware.Handler) httprouter.Handle {
	// OAuth 2.0 with email scope is registered as a default authenticator
	// by importing "github.com/luci/luci-go/appengine/gaeauth/server".
	// No need to setup an authenticator here.
	//
	// For authorization checks, we use per-service decorators; see
	// service registration code.
	return gaemiddleware.BaseProd(h)
}

//// Routes.

func init() {
	router := httprouter.New()
	gaemiddleware.InstallHandlers(router, base)
	router.GET("/", webBase(indexPage))

	var api prpc.Server
	crimson.RegisterGreeterServer(&api, &crimson.DecoratedGreeter{
		Service: &greeterService{},
		Prelude: checkAuthorizationPrpc,
	})
	discovery.Enable(&api)
	api.InstallHandlers(router, prpcBase)

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
