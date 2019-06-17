// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common implements common functionality for the Tricium service modules.
package common

import (
	"context"
	"net/http"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/appengine"
)

// Task queue names.
const (
	AnalysisResultsQueue = "bigquery-analysis-results-queue"
	AnalyzeQueue         = "analyze-queue"
	DriverQueue          = "driver-queue"
	FeedbackEventsQueue  = "bigquery-feedback-events-queue"
	GerritReporterQueue  = "gerrit-reporter-queue"
	LauncherQueue        = "launcher-queue"
	PollProjectQueue     = "poll-project-queue"
	TrackerQueue         = "tracker-queue"
)

// AppID returns the current App ID.
//
// The dev instance name is used for local dev app servers.
func AppID(c context.Context) string {
	if appengine.IsDevAppServer() {
		return "tricium-dev"
	}
	return info.AppID(c)
}

// ReportServerError reports back a server error (http code 500).
func ReportServerError(c *router.Context, err error) {
	logging.WithError(err).Errorf(c.Context, "HTTP 500")
	http.Error(c.Writer, "An internal server error occurred. We are working on it ;)",
		http.StatusInternalServerError)
}

// MiddlewareBase returns a middleware chain applied to ALL routes.
func MiddlewareBase() router.MiddlewareChain {
	return standard.Base()
}

// MiddlewareForInternal returns a middleware chain applied to internal routes.
//
// It assumes internal routes are protected by specifying 'login: admin'
// app.yaml.
func MiddlewareForInternal() router.MiddlewareChain {
	// TODO(vadimsh): Figure out how to assert that the handler is called by GAE
	// itself or by PubSub. That's how internal routes are supposed to be called.
	return MiddlewareBase().Extend(auth.Authenticate(anonymousMethod{}))
}

// TODO(qyearsley): Extract this to an appropriate place in luci-go so it might be re-used.
type anonymousMethod struct{}

func (m anonymousMethod) Authenticate(ctx context.Context, r *http.Request) (*auth.User, error) {
	return &auth.User{Identity: identity.AnonymousIdentity}, nil
}

// MiddlewareForUI returns a middleware chain intended for Web UI routes.
//
// It's same as MiddlewareBase, with addition of authentication based on
// cookies. It is supposed to be used for all routes that result in HTML pages.
//
// Anonymous access is still allowed. The handlers should do authorization
// checks by examining auth.CurrentIdentity(ctx) (it can be identity.Anonymous).
func MiddlewareForUI() router.MiddlewareChain {
	// Configure auth system to use cookies and actually attempt to do the
	// authentication. Finally, configure template system.
	return MiddlewareBase().Extend(auth.Authenticate(server.CookieAuth))
}

// MiddlewareForREST returns a middleware chain intended for REST API routes.
//
// It's same as MiddlewareBase, with addition of authentication based on
// OAuth2 access tokens. It is supposed to be used for all REST API routes.
//
// Anonymous access is still allowed. The handlers should do authorization
// checks by examining auth.CurrentIdentity(ctx) (it can be identity.Anonymous).
func MiddlewareForREST() router.MiddlewareChain {
	return MiddlewareBase().Extend(
		auth.Authenticate(&server.OAuth2Method{Scopes: []string{server.EmailScope}}),
	)
}

// MiddlewareForRPC returns a middleware chain intended for pRPC routes.
//
// It is identical to MiddlewareBase currently, since pRPC does its
// authentication (based on OAuth2 access tokens) internally.
func MiddlewareForRPC() router.MiddlewareChain {
	return MiddlewareBase()
}

// NewRPCServer returns preconfigured pRPC server that can host gRPC APIs.
//
// Usage:
//   srv := NewRPCServer()
//   someapi.RegisterSomeAPIServer(srv, ...)
//   ...
//   discovery.Enable(srv)
//   srv.InstallHandlers(router, MiddlewareForRPC())
func NewRPCServer() *prpc.Server {
	// TODO(vadimsh): Enable monitoring interceptor.
	// UnaryServerInterceptor: grpcmon.NewUnaryServerInterceptor(nil),
	return &prpc.Server{
		AccessControl: func(c context.Context, origin string) bool {
			return true
		},
	}
}
