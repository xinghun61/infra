// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"net/http"

	authServer "go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/config/appengine/gaeconfig"
	"go.chromium.org/luci/config/impl/filesystem"
	"go.chromium.org/luci/config/impl/remote"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/appengine"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
)

func init() {
	r := router.New()
	base := common.MiddlewareForInternal()

	// Tracker: handlers that perform actions while updating datastore.
	r.POST("/tracker/internal/worker-done", base, workerDoneHandler)
	r.POST("/tracker/internal/worker-launched", base, workerLaunchedHandler)
	r.POST("/tracker/internal/workflow-launched", base, workflowLaunchedHandler)
	r.GET("/tracker/internal/cron/bqlog/flush", base.Extend(gaemiddleware.RequireCron), bqFlushHandler)

	// Driver: handlers that trigger and collect tasks.
	r.POST("/driver/internal/trigger", base, triggerHandler)
	r.POST("/driver/internal/collect", base, collectHandler)
	// Devserver can't accept PubSub pushes, use manual PubSub pulls instead in development.
	if appengine.IsDevAppServer() {
		r.GET("/driver/internal/pull", base, pubsubPullHandler)
	} else {
		r.POST("/_ah/push-handlers/notify", base, pubsubPushHandler)
	}

	// Gerrit: handlers that interact with Gerrit.
	r.GET("/gerrit/internal/poll", base, pollHandler)
	r.POST("/gerrit/internal/poll-project", base, pollProjectHandler)
	r.POST("/gerrit/internal/report-results", base, reportResultsHandler)

	// Launcher: Handlers that initiate Tricium workflows.
	r.POST("/launcher/internal/launch", base, launchHandler)

	// Configure pRPC services.
	s := common.NewRPCServer()
	admin.RegisterTrackerServer(s, &trackerServer{})
	admin.RegisterDriverServer(s, &driverServer{})
	admin.RegisterReporterServer(s, &gerritReporterServer{})
	admin.RegisterLauncherServer(s, &launcherServer{})
	discovery.Enable(s)
	s.InstallHandlers(r, common.MiddlewareForRPC())

	// Configure config update cron job handler.
	configMiddleware := withRemoteConfigService
	if appengine.IsDevAppServer() {
		// For the dev appserver, always we use configs from the local filesystem.
		configMiddleware = withFilesystemConfigService
	}
	configUpdateMiddleware := standard.Base().Extend(
		auth.Authenticate(authServer.CookieAuth),
		configMiddleware,
		gaemiddleware.RequireCron)
	r.GET("/config/update", configUpdateMiddleware, UpdateHandler)

	http.DefaultServeMux.Handle("/", r)
}

// withRemoteConfigService changes the context c to use configs from luci-config.
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

// withFilesystemConfigService changes the context c to use local configs.
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

func bqFlushHandler(c *router.Context) {
	// Flush all BigQuery rows; rows for separate tables can be flushed
	// in parallel.
	err := parallel.FanOutIn(func(ch chan<- func() error) {
		ch <- func() error {
			_, err := common.ResultsLog.Flush(c.Context)
			return err
		}
		ch <- func() error {
			_, err := common.EventsLog.Flush(c.Context)
			return err
		}
	})
	if err != nil {
		http.Error(c.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	c.Writer.WriteHeader(http.StatusOK)
}
