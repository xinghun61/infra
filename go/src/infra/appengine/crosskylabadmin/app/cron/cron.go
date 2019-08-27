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
	"context"
	"fmt"
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend"
	"infra/appengine/crosskylabadmin/app/frontend/inventory"
)

// InstallHandlers installs handlers for cron jobs that are part of this app.
//
// All handlers serve paths under /internal/cron/*
// These handlers can only be called by appengine's cron service.
func InstallHandlers(r *router.Router, mwBase router.MiddlewareChain) {
	mwCron := mwBase.Extend(gaemiddleware.RequireCron)
	r.GET("/internal/cron/refresh-bots", mwCron, logAndSetHTTPErr(refreshBotsCronHandler))
	r.GET("/internal/cron/refresh-inventory", mwCron, logAndSetHTTPErr(refreshInventoryCronHandler))
	r.GET("/internal/cron/ensure-background-tasks", mwCron, logAndSetHTTPErr(ensureBackgroundTasksCronHandler))
	r.GET("/internal/cron/trigger-repair-on-idle", mwCron, logAndSetHTTPErr(triggerRepairOnIdleCronHandler))
	r.GET("/internal/cron/trigger-repair-on-repair-failed", mwCron, logAndSetHTTPErr(triggerRepairOnRepairFailedCronHandler))
	r.GET("/internal/cron/ensure-critical-pools-healthy", mwCron, logAndSetHTTPErr(ensureCriticalPoolsHealthy))

	// Generate repair or reset jobs for CrOS DUTs.
	r.GET("/internal/cron/push-bots-for-admin-tasks", mwCron, logAndSetHTTPErr(pushBotsForAdminTasksCronHandler))

	// for repair jobs of labstation.
	r.GET("/internal/cron/push-repair-jobs-for-labstations", mwCron, logAndSetHTTPErr(pushRepairJobsForLabstationsCronHandler))

	// Update device config asynchronously.
	r.GET("/internal/cron/update-device-configs", mwCron, logAndSetHTTPErr(updateDeviceConfigCronHandler))

	// Report Bot metrics.
	r.GET("/internal/cron/report-bots", mwCron, logAndSetHTTPErr(reportBotsCronHandler))

	r.GET("/internal/cron/push-inventory-to-queen", mwCron, logAndSetHTTPErr(pushInventoryToQueenCronHandler))
}

func updateDeviceConfigCronHandler(c *router.Context) (err error) {
	defer func() {
		updateDeviceConfigCronHandlerTick.Add(c.Context, 1, err == nil)
	}()
	inv := createInventoryServer(c)
	if _, err := inv.UpdateDeviceConfig(c.Context, &fleet.UpdateDeviceConfigRequest{}); err != nil {
		logging.Errorf(c.Context, "fail to update device config: %s", err.Error())
		return err
	}
	logging.Infof(c.Context, "update device config successfully")
	return nil
}

// pushBotsForAdminTasksCronHandler pushes bots that require admin tasks to bot queue.
func pushBotsForAdminTasksCronHandler(c *router.Context) (err error) {
	defer func() {
		pushBotsForAdminTasksCronHandlerTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisablePushBotsForAdminTasks() {
		logging.Infof(c.Context, "PushBotsForAdminTasks is disabled via config.")
		return nil
	}

	tsi := frontend.TrackerServerImpl{}
	if _, err := tsi.PushBotsForAdminTasks(c.Context, &fleet.PushBotsForAdminTasksRequest{}); err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully finished")
	return nil
}

// pushLabstationsForRepairCronHandler pushes bots that require admin tasks to bot queue.
func pushRepairJobsForLabstationsCronHandler(c *router.Context) (err error) {
	defer func() {
		pushRepairJobsForLabstationsCronHandlerTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisablePushLabstationsForRepair() {
		logging.Infof(c.Context, "PushLabstationsForRepair is disabled via config.")
		return nil
	}

	tsi := frontend.TrackerServerImpl{}
	if _, err := tsi.PushRepairJobsForLabstations(c.Context, &fleet.PushRepairJobsForLabstationsRequest{}); err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully finished")
	return nil
}

func reportBotsCronHandler(c *router.Context) (err error) {
	defer func() {
		reportBotsCronHandlerTick.Add(c.Context, 1, err == nil)
	}()

	tsi := frontend.TrackerServerImpl{}
	if _, err := tsi.ReportBots(c.Context, &fleet.ReportBotsRequest{}); err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully report bot metrics")
	return nil
}

// refreshBotsCronHandler refreshes the swarming bot information about the whole fleet.
func refreshBotsCronHandler(c *router.Context) (err error) {
	defer func() {
		refreshBotsTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisableRefreshBots() {
		logging.Infof(c.Context, "RefreshBots is disabled via config.")
		return nil
	}

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
func ensureBackgroundTasksCronHandler(c *router.Context) (err error) {
	defer func() {
		ensureBackgroundTasksTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisableEnsureBackgroundTasks() {
		logging.Infof(c.Context, "EnableBackgroundTasks is disabled via config.")
		return nil
	}

	ttypes := []fleet.TaskType{fleet.TaskType_Cleanup, fleet.TaskType_Reset, fleet.TaskType_Repair}
	tsi := frontend.TaskerServerImpl{}
	for _, ttype := range ttypes {
		resp, err := tsi.EnsureBackgroundTasks(c.Context, &fleet.EnsureBackgroundTasksRequest{
			Priority:  cfg.Cron.FleetAdminTaskPriority,
			TaskCount: cfg.Cron.EnsureTasksCount,
			Type:      ttype,
		})
		if err != nil {
			return err
		}
		logging.Infof(c.Context, "Scheduled background %s tasks for %d bots", ttype.String(), len(resp.BotTasks))
		numIncompleteBots := 0
		for _, bt := range resp.BotTasks {
			if len(bt.Tasks) != int(cfg.Cron.EnsureTasksCount) {
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
func triggerRepairOnIdleCronHandler(c *router.Context) (err error) {
	defer func() {
		triggerRepairOnIdleTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisableTriggerRepairOnIdle() {
		logging.Infof(c.Context, "TriggerRepairOnIdle is disabled via config.")
		return nil
	}

	tsi := frontend.TaskerServerImpl{}
	resp, err := tsi.TriggerRepairOnIdle(c.Context, &fleet.TriggerRepairOnIdleRequest{
		IdleDuration: cfg.Cron.RepairIdleDuration,
		Priority:     cfg.Cron.FleetAdminTaskPriority,
	})
	if err != nil {
		return err
	}
	bc, tc := countBotsAndTasks(resp)
	logging.Infof(c.Context, "Triggered %d tasks on %d bots", tc, bc)
	return nil
}

// triggerRepairOnIdleCronHandler triggers repair tasks on idle bots in the fleet.
func triggerRepairOnRepairFailedCronHandler(c *router.Context) (err error) {
	defer func() {
		triggerRepairOnRepairFailedTick.Add(c.Context, 1, err == nil)
	}()

	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisableTriggerRepairOnRepairFailed() {
		logging.Infof(c.Context, "TriggerRepairOnRepairFailed is disabled via config.")
		return nil
	}

	tsi := frontend.TaskerServerImpl{}
	resp, err := tsi.TriggerRepairOnRepairFailed(c.Context, &fleet.TriggerRepairOnRepairFailedRequest{
		Priority:            cfg.Cron.FleetAdminTaskPriority,
		TimeSinceLastRepair: cfg.Cron.RepairAttemptDelayDuration,
	})
	if err != nil {
		return err
	}
	bc, tc := countBotsAndTasks(resp)
	logging.Infof(c.Context, "Triggered %d tasks on %d bots", tc, bc)
	return nil
}

func pushInventoryToQueenCronHandler(c *router.Context) (err error) {
	defer func() {
		pushInventoryToQueenTick.Add(c.Context, 1, err == nil)
	}()
	inv := createInventoryServer(c)
	_, err = inv.PushInventoryToQueen(c.Context, &fleet.PushInventoryToQueenRequest{})
	return err
}

func logAndSetHTTPErr(f func(c *router.Context) error) func(*router.Context) {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}

func refreshInventoryCronHandler(c *router.Context) error {
	cfg := config.Get(c.Context)
	if cfg.RpcControl != nil && cfg.RpcControl.GetDisableRefreshInventory() {
		return nil
	}
	inv := createInventoryServer(c)
	_, err := inv.UpdateCachedInventory(c.Context, &fleet.UpdateCachedInventoryRequest{})
	return err
}

func ensureCriticalPoolsHealthy(c *router.Context) (err error) {
	cronCfg := config.Get(c.Context)
	if cronCfg.RpcControl.DisableEnsureCriticalPoolsHealthy {
		logging.Infof(c.Context, "EnsureCriticalPoolsHealthy is disabled via config.")
		return nil
	}

	cfg := config.Get(c.Context).GetCron().GetPoolBalancer()
	if cfg == nil {
		return errors.New("invalid pool balancer configuration")
	}

	inv := createInventoryServer(c)
	merr := make(errors.MultiError, 0)
	for _, target := range cfg.GetTargetPools() {
		resp, err := inv.EnsurePoolHealthyForAllModels(c.Context, &fleet.EnsurePoolHealthyForAllModelsRequest{
			TargetPool:       target,
			SparePool:        cfg.GetSparePool(),
			MaxUnhealthyDuts: cfg.GetMaxUnhealthyDuts(),
		})
		if err != nil {
			logging.Errorf(c.Context, "Error ensuring pool health for %s: %s", target, err.Error())
			merr = append(merr, errors.Annotate(err, "ensure critical pools healthy for pool %s", target).Err())
			continue
		}
		logging.Infof(c.Context, "Ensured pool health for target pool %s. Result %#v", target, resp)
	}
	return merr.First()
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

func createInventoryServer(c *router.Context) *inventory.ServerImpl {
	tracker := &frontend.TrackerServerImpl{}
	return &inventory.ServerImpl{
		GerritFactory: func(c context.Context, host string) (gerrit.GerritClient, error) {
			return clients.NewGerritClientAsSelf(c, host)
		},
		GitilesFactory: func(c context.Context, host string) (gitiles.GitilesClient, error) {
			return clients.NewGitilesClientAsSelf(c, host)
		},
		TrackerFactory: func() fleet.TrackerServer {
			return tracker
		},
	}
}
