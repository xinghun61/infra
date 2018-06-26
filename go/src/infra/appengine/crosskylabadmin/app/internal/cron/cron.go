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

package cron

import (
	"fmt"
	"math"
	"net/http"
	"time"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

// TODO(pprabhu) Move these to luci-config (and out of this internal package).
const (
	// crosskylabadminProdHost is the prod AE instance of this app.
	crosskylabadminProdHost = "chromeos-skylab-bot-fleet.appspot.com"
	// backgroundTasksCount is the number of background tasks maintained against each bot.
	backgroundTasksCount = 3
	// backgroundTasksPriority is the swarming task priority of the created background tasks.
	//
	// This must be numerically smaller (i.e. more important) than the default task priority of 20.
	backgroundTasksPriority = 10
)

// InitHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers do not enforce any authentication on the caller. Access should be
// restricted to admin users via appengine directives.
func InitHandlers(r *router.Router, mwBase router.MiddlewareChain) {
	mwCron := mwBase.Extend(gaemiddleware.RequireCron)
	r.GET("/internal/cron/refresh-bots", mwCron, sendHTTPErrorResponse(refreshBots))
	r.GET("/internal/cron/ensure-background-tasks", mwCron, sendHTTPErrorResponse(ensureBackgroundTasks))
}

// refreshBots refreshes the swarming bot information about the whole fleet.
//
// This handler can take up to 5 minutes to complete.
func refreshBots(c *router.Context) error {
	c.Context, _ = context.WithDeadline(c.Context, time.Now().Add(5*time.Minute))
	client, err := newTrackerClient(c.Context)
	if err != nil {
		return err
	}
	resp, err := client.RefreshBots(c.Context, &fleet.RefreshBotsRequest{})
	if err != nil {
		return errors.Annotate(err, "failed to refresh all bots").Err()
	}
	logging.Infof(c.Context, "Successfully refreshed %d bots", len(resp.DutIds))
	return nil
}

func sendHTTPErrorResponse(f func(c *router.Context) error) func(*router.Context) {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

// ensureBackgroundTasks ensures that the configured number of admin tasks
// are pending against the fleet.
//
// This handler can take up to 15 minutes to complete.
func ensureBackgroundTasks(c *router.Context) error {
	c.Context, _ = context.WithDeadline(c.Context, time.Now().Add(15*time.Minute))
	client, err := newTaskerClient(c.Context)
	if err != nil {
		return err
	}

	merr := errors.MultiError{}
	merr = append(merr, ensureBackgroundTasksOfType(c.Context, client, fleet.TaskType_Cleanup, backgroundTasksCount, backgroundTasksPriority))
	merr = append(merr, ensureBackgroundTasksOfType(c.Context, client, fleet.TaskType_Repair, backgroundTasksCount, backgroundTasksPriority))
	merr = append(merr, ensureBackgroundTasksOfType(c.Context, client, fleet.TaskType_Reset, backgroundTasksCount, backgroundTasksPriority))
	if merr.First() != nil {
		return merr
	}
	return nil
}

func ensureBackgroundTasksOfType(c context.Context, client fleet.TaskerClient, ttype fleet.TaskType, count int, priority int) error {
	// This value will come from luci-config eventually, so we must validate here.
	if int(int32(count)) != count {
		return fmt.Errorf("Requested too many tasks: %d. Must be less than %d", count, math.MaxInt32)
	}

	resp, err := client.EnsureBackgroundTasks(c, &fleet.EnsureBackgroundTasksRequest{
		Priority:  int64(priority),
		TaskCount: int32(count),
		Type:      ttype,
	})
	if err != nil {
		return errors.Annotate(err, "failed to ensure background %s tasks", ttype.String()).Err()
	}
	logging.Infof(c, "Scheduled background %s tasks for %d bots", ttype.String(), len(resp.BotTasks))
	numIncompleteBots := 0
	for _, bt := range resp.BotTasks {
		if len(bt.Tasks) != count {
			numIncompleteBots = numIncompleteBots + 1
		}
	}
	if numIncompleteBots > 0 {
		return fmt.Errorf("Scheduled insufficient tasks for %d / %d bots", numIncompleteBots, len(resp.BotTasks))
	}
	return nil
}

func newTrackerClient(c context.Context) (fleet.TrackerClient, error) {
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, errors.Annotate(err, "could not get RPC transport").Err()
	}
	return fleet.NewTrackerPRPCClient(&prpc.Client{
		C:    &http.Client{Transport: t},
		Host: crosskylabadminProdHost,
	}), nil
}

func newTaskerClient(c context.Context) (fleet.TaskerClient, error) {
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, errors.Annotate(err, "could not get RPC transport").Err()
	}
	return fleet.NewTaskerPRPCClient(&prpc.Client{
		C:    &http.Client{Transport: t},
		Host: crosskylabadminProdHost,
	}), nil
}
