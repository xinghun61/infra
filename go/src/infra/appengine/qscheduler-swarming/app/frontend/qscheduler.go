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
	"context"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/swarming"

	"github.com/pkg/errors"
	"go.chromium.org/gae/service/datastore"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
)

// QSchedulerState encapsulates the state of a scheduler.
type QSchedulerState struct {
	schedulerID string
	scheduler   *scheduler.Scheduler
	reconciler  *reconciler.State
	config      *qscheduler.SchedulerPoolConfig
}

// QSchedulerServerImpl implements the QSchedulerServer interface.
type QSchedulerServerImpl struct {
	// TODO(akeshet): Implement in-memory cache of SchedulerPool struct, so that
	// we don't need to load and re-persist its state on every call.
	// TODO(akeshet): Implement request batching for AssignTasks and NotifyTasks.
	// TODO(akeshet): Determine if go.chromium.org/luci/server/caching has a
	// solution for in-memory caching like this.
}

// AssignTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (*swarming.AssignTasksResponse, error) {
	var response *swarming.AssignTasksResponse

	doAssign := func(ctx context.Context) error {
		sp, err := load(ctx, r.SchedulerId)
		if err != nil {
			return err
		}

		idles := make([]*reconciler.IdleWorker, len(r.IdleBots))
		for i, v := range r.IdleBots {
			idles[i] = &reconciler.IdleWorker{
				ID: v.BotId,
				// TODO(akeshet): Compute provisionable labels properly. This should actually
				// be the workers label set minus the scheduler pool's label set.
				ProvisionableLabels: v.Dimensions,
			}
		}

		a, err := sp.reconciler.AssignTasks(ctx, sp.scheduler, tutils.Timestamp(r.Time), idles...)
		if err != nil {
			return nil
		}

		assignments := make([]*swarming.TaskAssignment, len(a))
		for i, v := range a {
			assignments[i] = &swarming.TaskAssignment{
				BotId:  v.WorkerID,
				TaskId: v.RequestID,
			}
		}
		if err := save(ctx, sp); err != nil {
			return err
		}
		response = &swarming.AssignTasksResponse{Assignments: assignments}
		return nil
	}

	if err := datastore.RunInTransaction(ctx, doAssign, nil); err != nil {
		return nil, err
	}

	return response, nil
}

// GetCancellations implements QSchedulerServer.
func (s *QSchedulerServerImpl) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (*swarming.GetCancellationsResponse, error) {
	sp, err := load(ctx, r.SchedulerId)
	if err != nil {
		return nil, err
	}

	c := sp.reconciler.Cancellations(ctx)
	rc := make([]*swarming.GetCancellationsResponse_Cancellation, len(c))
	for i, v := range c {
		rc[i] = &swarming.GetCancellationsResponse_Cancellation{BotId: v.WorkerID, TaskId: v.RequestID}
	}
	return &swarming.GetCancellationsResponse{Cancellations: rc}, nil
}

// NotifyTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (*swarming.NotifyTasksResponse, error) {

	doNotify := func(ctx context.Context) error {
		sp, err := load(ctx, r.SchedulerId)
		if err != nil {
			return err
		}

		for _, n := range r.Notifications {
			var t reconciler.TaskUpdate_Type
			switch n.Task.State {
			case swarming.TaskState_PENDING:
				t = reconciler.TaskUpdate_NEW
			case swarming.TaskState_RUNNING:
				t = reconciler.TaskUpdate_ASSIGNED
			default:
				return errors.Errorf("unknown or not handleable swarming state %s", n.Task.State)
			}
			if n.Task.State == swarming.TaskState_PENDING {
				t = reconciler.TaskUpdate_NEW
			} else if n.Task.State == swarming.TaskState_RUNNING {
				t = reconciler.TaskUpdate_ASSIGNED
			}
			// TODO(akeshet): Validate that new tasks have dimensions that match the
			// worker pool dimensions for this scheduler pool.
			update := &reconciler.TaskUpdate{
				// TODO(akeshet): implement me. This will be based upon task tags.
				AccountId: "",
				// TODO(akeshet): implement me properly. This should be a separate field
				// of the task state, not the notification time.
				EnqueueTime: n.Time,
				// TODO(akeshet): implement me properly. This should be determined by the
				// difference between the first and last task slice of the task.
				ProvisionableLabels: []string{},
				RequestId:           n.Task.Id,
				Time:                n.Time,
				Type:                t,
				WorkerId:            n.Task.BotId,
			}
			if err := sp.reconciler.Notify(ctx, sp.scheduler, update); err != nil {
				return err
			}
		}
		return save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, doNotify, nil); err != nil {
		return nil, err
	}
	return &swarming.NotifyTasksResponse{}, nil
}
