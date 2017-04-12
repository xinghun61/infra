// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP server that handles requests to default
// module.
package frontend

import (
	"database/sql"
	"net/http"
	"strings"

	"github.com/golang/protobuf/proto"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/grpc/discovery"
	"github.com/luci/luci-go/grpc/grpcutil"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"

	crimson "infra/crimson/proto"
	"infra/crimson/server/crimsondb"
)

// templateBundle is used to render HTML templates. It provides a base args
// passed to all templates.
var (
	dbHandle *sql.DB
	// People with read/write access to the database (c-i-a group)
	rwGroup = "crimson"

	templateBundle = &templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: info.IsDevAppServer,
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
				"AppVersion":  strings.Split(info.VersionID(c), ".")[0],
				"IsAnonymous": auth.CurrentIdentity(c) == identity.AnonymousIdentity,
				"IsAdmin":     isAdmin,
				"User":        auth.CurrentUser(c),
				"LoginURL":    loginURL,
				"LogoutURL":   logoutURL,
			}, nil
		},
	}
)

// Auth middleware. Hard fails when user is not authorized.
func requireAuthWeb(c *router.Context, next router.Handler) {
	if auth.CurrentIdentity(c.Context) == identity.AnonymousIdentity {
		loginURL, err := auth.LoginURL(c.Context, "/")
		if err != nil {
			logging.Errorf(c.Context, "Failed to get login URL")
			http.Error(c.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		logging.Infof(c.Context, "Redirecting to %s", loginURL)
		http.Redirect(c.Writer, c.Request, loginURL, 302)
		return
	}

	isGoogler, err := auth.IsMember(c.Context, rwGroup)
	if err != nil {
		c.Writer.WriteHeader(http.StatusInternalServerError)
		logging.Errorf(c.Context, "Failed to get group membership.")
		return
	}
	if isGoogler {
		next(c)
		return
	}

	templates.MustRender(c.Context, c.Writer, "pages/access_denied.html", nil)
}

func addDbToContext(c *router.Context, next router.Handler) {
	c.Context = crimsondb.UseDB(c.Context, dbHandle)
	next(c)
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

func base() router.MiddlewareChain {
	methods := auth.Authenticator{
		server.CookieAuth,
	}
	return gaemiddleware.BaseProd().Extend(
		templates.WithTemplates(templateBundle),
		auth.Use(methods),
		auth.Authenticate,
	)
}

// webBase sets up authentication/authorization for http requests.
func webBase() router.MiddlewareChain {
	return base().Extend(requireAuthWeb)
}

// prpcBase returns the middleware for pRPC API handlers.
func prpcBase() router.MiddlewareChain {
	// OAuth 2.0 with email scope is registered as a default authenticator
	// by importing "github.com/luci/luci-go/appengine/gaeauth/server".
	// No need to setup an authenticator here.
	//
	// Authorization is checked in checkAuthorizationPrpc using a
	// service decorator.
	return gaemiddleware.BaseProd().Extend(addDbToContext)
}

//// Routes.

func init() {

	// Open DB connection.
	// Declare 'err' here otherwise the next line shadows the global 'dbHandle'
	var err error
	dbHandle, err = crimsondb.GetDBHandle()
	if err != nil {
		logging.Errorf(context.Background(),
			"Failed to connect to CloudSQL: %v", err)
		return
	}

	r := router.New()
	gaemiddleware.InstallHandlers(r)
	r.GET("/", webBase(), indexPage)

	var api prpc.Server
	crimson.RegisterCrimsonServer(&api, &crimson.DecoratedCrimson{
		Service: &crimsonService{},
		Prelude: checkAuthorizationPrpc,
	})
	discovery.Enable(&api)
	api.InstallHandlers(r, prpcBase())

	http.DefaultServeMux.Handle("/", r)
}

//// Handlers.

func indexPage(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", nil)
}
