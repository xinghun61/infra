// Copyright 2019 The LUCI Authors.
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

package cron

import (
	"fmt"
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
)

// http500res sets status to 500 and puts a given error message in response.
func http500res(c *router.Context, e error, msg string, args ...interface{}) {
	args = append(args, e)
	body := fmt.Sprintf(msg, args...)
	logging.Errorf(c.Context, "HTTP %d: %s", 500, body)
	http.Error(c.Writer, body, 500)
}

// http200res sets status to 200 and puts "OK" in response.
func http200res(c *router.Context) {
	c.Writer.Header().Set("Content-Type", "text/plain; charset=utf-8")
	c.Writer.WriteHeader(200)
	fmt.Fprintln(c.Writer, "OK")
}

func updateAssigners(c *router.Context) {
	ctx := c.Context
	cfgs := config.Get(ctx).Assigners
	rev := config.GetConfigRevision(ctx)

	// TODO(crbug/967549) - revalidate the configs
	if err := backend.UpdateAssigners(ctx, cfgs, rev); err != nil {
		http500res(c, err, "failed to update assigners")
		return
	}
	http200res(c)
}

func scheduleAssigners(c *router.Context) {
	ctx := c.Context
	aes, err := backend.GetAllAssigners(ctx)
	if err != nil {
		http500res(c, err, "failed to retrieve assigners.")
		return
	}

	tasks := make([]*tq.Task, 0, len(aes))
	for _, ae := range aes {
		tasks = append(tasks, &tq.Task{
			Payload: &backend.ScheduleAssignerTask{
				AssignerId: ae.ID,
			},
		})
	}
	if err := util.GetDispatcher(ctx).AddTask(ctx, tasks...); err != nil {
		http500res(c, err, "failed to add tasks to task queue")
		return
	}
	http200res(c)
}

//
// InstallHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers can only be called by appengine's cron service.
func InstallHandlers(r *router.Router, dispatcher *tq.Dispatcher, mwBase router.MiddlewareChain) {
	m := mwBase.Extend(gaemiddleware.RequireCron)
	m = m.Extend(func(rc *router.Context, next router.Handler) {
		rc.Context = util.SetDispatcher(rc.Context, dispatcher)
		next(rc)
	})
	r.GET("/internal/cron/update-assigners", m, updateAssigners)
	r.GET("/internal/cron/schedule-assigners", m, scheduleAssigners)
}
