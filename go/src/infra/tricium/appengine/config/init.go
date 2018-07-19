// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package config implements the Tricium config module.
package config

import (
	"net/http"

	"golang.org/x/net/context"
	"google.golang.org/appengine"

	authServer "go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/config/appengine/gaeconfig"
	"go.chromium.org/luci/config/impl/filesystem"
	"go.chromium.org/luci/config/impl/remote"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

func init() {
	r := router.New()

	// Configure pRPC server.
	s := common.NewRPCServer()
	admin.RegisterConfigServer(s, server)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	// Configure config update cron job handler.
	configMiddleware := withRemoteConfigService
	if appengine.IsDevAppServer() {
		// For the dev appserver, always we use configs from the local filesystem.
		configMiddleware = withFilesystemConfigService
	}
	mw := standard.Base().Extend(
		auth.Authenticate(authServer.CookieAuth),
		configMiddleware,
		gaemiddleware.RequireCron)
	r.GET("/config/update", mw, UpdateHandler)

	http.DefaultServeMux.Handle("/", r)
}

func withRemoteConfigService(c *router.Context, next router.Handler) {
	s, err := gaeconfig.FetchCachedSettings(c.Context)
	if err != nil {
		c.Writer.WriteHeader(http.StatusInternalServerError)
		logging.WithError(err).Errorf(c.Context, "Failed to retrieve cached settings")
		return
	}
	iface := remote.New(s.ConfigServiceHost, false, func(c context.Context) (*http.Client, error) {
		t, err := auth.GetRPCTransport(c, auth.AsSelf)
		if err != nil {
			return nil, err
		}
		return &http.Client{Transport: t}, nil
	})
	c.Context = config.WithConfigService(c.Context, iface)
	next(c)
}

func withFilesystemConfigService(c *router.Context, next router.Handler) {
	iface, err := filesystem.New("../devcfg")
	if err != nil {
		c.Writer.WriteHeader(http.StatusInternalServerError)
		logging.WithError(err).Errorf(c.Context, "Failed to load local config files.")
		return
	}
	c.Context = config.WithConfigService(c.Context, iface)
	next(c)
}
