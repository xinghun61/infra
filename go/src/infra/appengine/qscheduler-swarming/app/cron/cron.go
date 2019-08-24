// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Package cron implements handlers for appengine cron targets in this app.
package cron

import (
	"net/http"
	"time"

	"infra/appengine/qscheduler-swarming/app/frontend"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	swarming "infra/swarming"

	"github.com/pkg/errors"

	"go.chromium.org/luci/appengine/bqlog"
	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/server/router"

	"infra/qscheduler/qslib/tutils"
)

// InstallHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers can only be called by appengine's cron service.
func InstallHandlers(r *router.Router, mwBase router.MiddlewareChain, bqlogTasks *bqlog.Log) {
	mwCron := mwBase.Extend(gaemiddleware.RequireCron)
	r.GET("/internal/cron/refresh-schedulers", mwCron, logAndSetHTTPError(refreshSchedulers))
	r.GET("/internal/cron/flush-bq-events", mwCron, logAndSetHTTPError(func(c *router.Context) error {
		_, err := bqlogTasks.Flush(c.Context)
		return err
	}))
}

func logAndSetHTTPError(f func(c *router.Context) error) func(*router.Context) {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

func refreshSchedulers(c *router.Context) error {
	ctx := c.Context
	IDs, err := nodestore.List(ctx)
	if err != nil {
		return err
	}

	ts := tutils.TimestampProto(time.Now())
	for _, sid := range IDs {
		// Refreshing a scheduler is equivalent to calling AssignTasks on it with no
		// idle bots.
		req := &swarming.AssignTasksRequest{SchedulerId: sid, Time: ts}

		s := &frontend.BasicQSchedulerServer{}
		if _, err := s.AssignTasks(ctx, req); err != nil {
			return errors.Wrap(err, "unable to refresh scheduler via AssignTasks")
		}
	}

	return nil
}
