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

package frontend

import (
	"fmt"
	"net/url"
	"strings"
	"sync"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
)

const (
	// luciferToolsDeploymentPath is the well known path to infra tools deployed on the drone.
	luciferToolsDeploymentPath = "/opt/infra-tools/usr/bin"
	// skylabSwarmingWrokerPath is the path to the binary on the drone
	// that is the entry point of all tasks.
	skylabSwarmingWorkerPath = luciferToolsDeploymentPath + "/skylab_swarming_worker"
)

// commonTaskTags are used to annotate all tasks created by tasker.
var commonTaskTags = []string{luciProjectTag, fleetAdminTaskTag}

// TaskerServerImpl implements the fleet.TaskerServer interface.
type TaskerServerImpl struct {
	clients.SwarmingFactory
}

// TriggerRepairOnIdle implements the fleet.TaskerService method.
func (tsi *TaskerServerImpl) TriggerRepairOnIdle(c context.Context, req *fleet.TriggerRepairOnIdleRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	sc, err := tsi.SwarmingClient(c, swarmingInstance)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	bses, err := getBotSummariesFromDatastore(c, req.Selectors)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain requested bots from datastore").Err()
	}
	return createTasksPerBot(bses, func(bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
		return triggerRepairOnIdleForBot(c, sc, req, bse)
	})
}

func triggerRepairOnIdleForBot(c context.Context, sc clients.SwarmingClient, req *fleet.TriggerRepairOnIdleRequest, bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
	idle, err := getIdleDuration(c, sc, bse.BotID)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get idle time for bot %q", bse.BotID).Err()
	}

	// Check existing tasks even before checking for trigger condition so that we
	// never lie about tasks we _have_ already created.
	tags := withCommonTags(fmt.Sprintf("idle_task:%s", bse.DutID))
	oldTasks, err := sc.ListRecentTasks(c, tags, "PENDING", 1)
	if err != nil {
		return nil, errors.Annotate(err, "failed to list existing on-idle tasks triggered for dut %s", bse.DutID).Err()
	}
	if len(oldTasks) > 0 {
		return repairTasksWithIDs(bse.DutID, []string{oldTasks[0].TaskId}), nil
	}

	if idle != nil && idle.Seconds < req.IdleDuration.Seconds {
		return repairTasksWithIDs(bse.DutID, []string{}), nil
	}

	tid, err := sc.CreateTask(c, &clients.SwarmingCreateTaskArgs{
		Cmd:                  luciferAdminTaskCmd(fleet.TaskType_Repair),
		DutID:                bse.DutID,
		DutState:             "ready",
		ExecutionTimeoutSecs: backgroundTaskExecutionTimeoutSecs,
		ExpirationSecs:       backgroundTaskExpirationSecs,
		Pool:                 swarmingBotPool,
		Priority:             req.Priority,
		Tags:                 tags,
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to create task for dut %s", bse.DutID).Err()
	}

	return repairTasksWithIDs(bse.DutID, []string{tid}), nil
}

// TriggerRepairOnRepairFailed implements the fleet.TaskerService method.
func (tsi *TaskerServerImpl) TriggerRepairOnRepairFailed(c context.Context, req *fleet.TriggerRepairOnRepairFailedRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	sc, err := tsi.SwarmingClient(c, swarmingInstance)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	bses, err := getBotSummariesFromDatastore(c, req.Selectors)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain requested bots from datastore").Err()
	}
	return createTasksPerBot(bses, func(bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
		return triggerRepairOnRepairFailedForBot(c, sc, req, bse)
	})
}

func triggerRepairOnRepairFailedForBot(c context.Context, sc clients.SwarmingClient, req *fleet.TriggerRepairOnRepairFailedRequest, bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
	bs, err := bse.Decode()
	if err != nil {
		return nil, errors.Annotate(err, "failed to decode bot summary entity for bot %s", bse.BotID).Err()
	}
	if bs.DutState != fleet.DutState_RepairFailed {
		return repairTasksWithIDs(bse.DutID, []string{}), nil
	}

	tags := withCommonTags(fmt.Sprintf("repair_failed_task:%s", bse.DutID))
	// A repair task should only be created if enough time has passed since the last attempt,
	// irrespective of the state the old task is in.
	oldTasks, err := sc.ListRecentTasks(c, tags, "", 1)
	if err != nil {
		return nil, errors.Annotate(err, "failed to list existing on-idle tasks triggered for dut %s", bse.DutID).Err()
	}

	if len(oldTasks) > 0 {
		ot := oldTasks[0]
		if ot.State == "PENDING" || ot.State == "RUNNING" {
			return repairTasksWithIDs(bse.DutID, []string{ot.TaskId}), nil
		}
		switch t, err := clients.TimeSinceBotTask(ot); {
		case err != nil:
			return nil, errors.Annotate(err, "failed to determine time since last attempt").Err()
		case t != nil && t.Seconds < req.TimeSinceLastRepair.Seconds:
			return repairTasksWithIDs(bse.DutID, []string{}), nil
		default:
			// old tasks are too old, must create new.
		}
	}

	tid, err := sc.CreateTask(c, &clients.SwarmingCreateTaskArgs{
		Cmd:                  luciferAdminTaskCmd(fleet.TaskType_Repair),
		DutID:                bse.DutID,
		DutState:             "repair_failed",
		ExecutionTimeoutSecs: backgroundTaskExecutionTimeoutSecs,
		ExpirationSecs:       backgroundTaskExpirationSecs,
		Pool:                 swarmingBotPool,
		Priority:             req.Priority,
		Tags:                 tags,
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to create task for dut %s", bse.DutID).Err()
	}

	return repairTasksWithIDs(bse.DutID, []string{tid}), nil
}

// EnsureBackgroundTasks implements the fleet.TaskerService method.
func (tsi *TaskerServerImpl) EnsureBackgroundTasks(c context.Context, req *fleet.EnsureBackgroundTasksRequest) (resp *fleet.TaskerTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()

	bses, err := getBotSummariesFromDatastore(c, req.Selectors)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain requested bots from datastore").Err()
	}

	sc, err := tsi.SwarmingClient(c, swarmingInstance)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	return createTasksPerBot(bses, func(bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
		return ensureBackgroundTasksForBot(c, sc, req, bse)
	})
}

var dutStateForTask = map[fleet.TaskType]string{
	fleet.TaskType_Cleanup: "needs_cleanup",
	fleet.TaskType_Repair:  "needs_repair",
	fleet.TaskType_Reset:   "needs_reset",
}

func ensureBackgroundTasksForBot(c context.Context, sc clients.SwarmingClient, req *fleet.EnsureBackgroundTasksRequest, bse *fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error) {
	ts := make([]*fleet.TaskerTask, 0, req.TaskCount)
	tags := withCommonTags(fmt.Sprintf("background_task:%s_%s", req.Type.String(), bse.DutID))
	oldTasks, err := sc.ListRecentTasks(c, tags, "PENDING", int(req.TaskCount))
	if err != nil {
		return nil, errors.Annotate(err, "Failed to list existing tasks of type %s for dut %s",
			req.Type.String(), bse.DutID).Err()
	}
	for _, ot := range oldTasks {
		ts = append(ts, &fleet.TaskerTask{
			TaskUrl: swarmingURLForTask(ot.TaskId),
			Type:    req.Type,
		})
	}

	newTaskCount := int(req.TaskCount) - len(ts)
	for i := 0; i < newTaskCount; i++ {
		tid, err := sc.CreateTask(c, &clients.SwarmingCreateTaskArgs{
			Cmd:                  luciferAdminTaskCmd(req.Type),
			DutID:                bse.DutID,
			DutState:             dutStateForTask[req.Type],
			ExecutionTimeoutSecs: backgroundTaskExecutionTimeoutSecs,
			ExpirationSecs:       backgroundTaskExpirationSecs,
			Pool:                 swarmingBotPool,
			Priority:             req.Priority,
			Tags:                 tags,
		})
		if err != nil {
			return nil, errors.Annotate(err, "Error when creating %dth task for dut %q", i+1, bse.DutID).Err()
		}
		ts = append(ts, &fleet.TaskerTask{
			TaskUrl: swarmingURLForTask(tid),
			Type:    req.Type,
		})
	}
	return &fleet.TaskerBotTasks{
		DutId: bse.DutID,
		Tasks: ts,
	}, nil
}

// createTasksPerBot uses worker() to create tasks for each bot in bses.
//
// worker() must accept a fleetBotSummaryEntity and create tasks for the corresponding bot.
func createTasksPerBot(bses []*fleetBotSummaryEntity, worker func(*fleetBotSummaryEntity) (*fleet.TaskerBotTasks, error)) (*fleet.TaskerTasksResponse, error) {
	// Protects access to botTasks
	m := &sync.Mutex{}
	botTasks := make([]*fleet.TaskerBotTasks, 0, len(bses))
	err := parallel.WorkPool(clients.MaxConcurrentSwarmingCalls, func(workC chan<- func() error) {
		for i := range bses {
			// In-scope variable for goroutine closure.
			bse := bses[i]
			workC <- func() error {
				bt, err := worker(bse)
				if bt != nil {
					m.Lock()
					defer m.Unlock()
					botTasks = append(botTasks, bt)
				}
				return err
			}
		}
	})
	if err != nil {
		return nil, err
	}
	return &fleet.TaskerTasksResponse{
		BotTasks: botTasks,
	}, nil
}

func repairTasksWithIDs(dutID string, taskIDs []string) *fleet.TaskerBotTasks {
	tasks := make([]*fleet.TaskerTask, 0, len(taskIDs))
	for _, tid := range taskIDs {
		tasks = append(tasks, &fleet.TaskerTask{
			TaskUrl: swarmingURLForTask(tid),
			Type:    fleet.TaskType_Repair,
		})
	}
	return &fleet.TaskerBotTasks{
		DutId: dutID,
		Tasks: tasks,
	}
}

func luciferAdminTaskCmd(ttype fleet.TaskType) []string {
	return []string{
		skylabSwarmingWorkerPath,
		"-task-name", fmt.Sprintf("admin_%s", strings.ToLower(ttype.String())),
	}
}

func withCommonTags(ts ...string) []string {
	tags := make([]string, 0, len(ts)+len(commonTaskTags))
	tags = append(tags, commonTaskTags...)
	tags = append(tags, ts...)
	return tags
}

func swarmingURLForTask(tid string) string {
	u := url.URL{
		Scheme: "https",
		Host:   swarmingInstance,
		Path:   "task",
	}
	q := u.Query()
	q.Set("id", tid)
	u.RawQuery = q.Encode()
	return u.String()
}
