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
//
// All actual logic related to fleet management should be implemented in the
// main fleet API. These handlers should only encapsulate the following bits of
// logic:
// - Calling other API as the appengine service account user.
// - Translating luci-config driven admin task parameters.
package cron

import (
	"fmt"
	"math"
	"net/http"
	"time"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/server/router"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/frontend"
)

// TODO(pprabhu) Move these to luci-config (and out of this package).
const (
	// crosskylabadminProdHost is the prod AE instance of this app.
	crosskylabadminProdHost = "chromeos-skylab-bot-fleet.appspot.com"

	// fleetAdminTaskPriority is the swarming task priority of the created background tasks.
	//
	// This must be numerically smaller (i.e. more important) than Skylab's test
	// task priority range [49-255] and numerically larger than the minimum
	// allowed Swarming priority (20) for non administrator users.
	fleetAdminTaskPriority = 30
	// ensureTasksCount is the number of background tasks maintained against each bot.
	ensureTasksCount = 3
	// repairIdleDuration is the duration for which a bot in the fleet must have
	// been idle for a repair task to be created against it.
	repairIdleDuration = 10 * time.Minute
	// repairAttemptDelayDuration is the time between successive attempts at repairing
	// repair failed bots in the fleet.
	repairAttemptDelayDuration = 1 * time.Hour
)

const (
	// cronTQ is the name of the push queue servicing cron requests.
	cronTQ = "crons"
)

// InstallHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers can only be called by appengine's cron service.
func InstallHandlers(r *router.Router, mwBase router.MiddlewareChain) {
	mwCron := mwBase.Extend(gaemiddleware.RequireCron)
	r.GET("/internal/cron/refresh-bots", mwCron, logAndSetHTTPErr(refreshBotsCronHandler))
	r.GET("/internal/cron/ensure-background-tasks", mwCron, logAndSetHTTPErr(ensureBackgroundTasksCronHandler))
	r.GET("/internal/cron/trigger-repair-on-idle", mwCron, logAndSetHTTPErr(triggerRepairOnIdleCronHandler))
	r.GET("/internal/cron/trigger-repair-on-repair-failed", mwCron, logAndSetHTTPErr(triggerRepairOnRepairFailedCronHandler))
}

// refreshBotsCronHandler refreshes the swarming bot information about the whole fleet.
func refreshBotsCronHandler(c *router.Context) error {
	tsi := frontend.TrackerServerImpl{}
	resp, err := tsi.RefreshBots(c.Context, &fleet.RefreshBotsRequest{})
	if err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully refreshed %d bots", len(resp.DutIds))
	return nil
}

// ensureBackgroundTasksCronHandler ensures that the configured number of admin tasks
// are pending against the fleet.
func ensureBackgroundTasksCronHandler(c *router.Context) error {
	count := int32(ensureTasksCount)
	if int(count) != ensureTasksCount {
		return fmt.Errorf("Requested too many tasks: %d. Must be less than %d", count, math.MaxInt32)
	}

	ttypes := []fleet.TaskType{fleet.TaskType_Cleanup, fleet.TaskType_Reset, fleet.TaskType_Repair}
	tsi := frontend.TaskerServerImpl{}
	for _, ttype := range ttypes {
		resp, err := tsi.EnsureBackgroundTasks(c.Context, &fleet.EnsureBackgroundTasksRequest{
			Priority:  int64(fleetAdminTaskPriority),
			TaskCount: count,
			Type:      ttype,
		})
		if err != nil {
			return err
		}
		logging.Infof(c.Context, "Scheduled background %s tasks for %d bots", ttype.String(), len(resp.BotTasks))
		numIncompleteBots := 0
		for _, bt := range resp.BotTasks {
			if len(bt.Tasks) != int(count) {
				numIncompleteBots = numIncompleteBots + 1
			}
		}
		if numIncompleteBots > 0 {
			return fmt.Errorf("Scheduled insufficient %s tasks for %d / %d bots", ttype.String(), numIncompleteBots, len(resp.BotTasks))
		}
	}
	return nil
}

// triggerRepairOnIdleCronHandler triggers repair tasks on idle bots in the fleet.
func triggerRepairOnIdleCronHandler(c *router.Context) error {
	tsi := frontend.TaskerServerImpl{}
	resp, err := tsi.TriggerRepairOnIdle(c.Context, &fleet.TriggerRepairOnIdleRequest{
		IdleDuration: google.NewDuration(repairIdleDuration),
		Priority:     int64(fleetAdminTaskPriority),
	})
	if err != nil {
		return err
	}
	bc, tc := countBotsAndTasks(resp)
	logging.Infof(c.Context, "Triggered %d tasks on %d bots", tc, bc)
	return nil
}

// triggerRepairOnIdleCronHandler triggers repair tasks on idle bots in the fleet.
func triggerRepairOnRepairFailedCronHandler(c *router.Context) error {
	tsi := frontend.TaskerServerImpl{}
	resp, err := tsi.TriggerRepairOnRepairFailed(c.Context, &fleet.TriggerRepairOnRepairFailedRequest{
		Priority:            int64(fleetAdminTaskPriority),
		TimeSinceLastRepair: google.NewDuration(repairAttemptDelayDuration),
	})
	if err != nil {
		return err
	}
	bc, tc := countBotsAndTasks(resp)
	logging.Infof(c.Context, "Triggered %d tasks on %d bots", tc, bc)
	return nil
}

func logAndSetHTTPErr(f func(c *router.Context) error) func(*router.Context) {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

func countBotsAndTasks(resp *fleet.TaskerTasksResponse) (int, int) {
	bc := 0
	tc := 0
	for _, bt := range resp.BotTasks {
		bc++
		tc += len(bt.Tasks)
	}
	return bc, tc
}
