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
	"fmt"
	"sort"

	"infra/appengine/qscheduler-swarming/app/entities"
	"infra/swarming"

	"github.com/pkg/errors"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/logging"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
)

// AccountIDTagKey is the key used in Task tags to specify which quotascheduler
// account the task should be charged to.
const AccountIDTagKey = "qs_account"

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
		sp, err := entities.Load(ctx, r.SchedulerId)
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

		a, err := sp.Reconciler.AssignTasks(ctx, sp.Scheduler, tutils.Timestamp(r.Time), idles...)
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
		if err := entities.Save(ctx, sp); err != nil {
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
	sp, err := entities.Load(ctx, r.SchedulerId)
	if err != nil {
		return nil, err
	}

	c := sp.Reconciler.Cancellations(ctx)
	rc := make([]*swarming.GetCancellationsResponse_Cancellation, len(c))
	for i, v := range c {
		rc[i] = &swarming.GetCancellationsResponse_Cancellation{BotId: v.WorkerID, TaskId: v.RequestID}
	}
	return &swarming.GetCancellationsResponse{Cancellations: rc}, nil
}

// NotifyTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (*swarming.NotifyTasksResponse, error) {

	doNotify := func(ctx context.Context) error {
		sp, err := entities.Load(ctx, r.SchedulerId)
		if err != nil {
			return err
		}

		if sp.Config == nil {
			return errors.Errorf("Scheduler with id %s has nil config.", r.SchedulerId)
		}

		for _, n := range r.Notifications {
			var t reconciler.TaskInstant_State
			var ok bool
			if t, ok = toTaskInstantState(n.Task.State); !ok {
				err := fmt.Sprintf("Invalid notification with unhandled state %s.", n.Task.State)
				logging.Warningf(ctx, err)
				sp.Reconciler.TaskError(n.Task.Id, err)
				continue
			}

			var provisionableLabels []string
			var accountID string
			// ProvisionableLabels attribute only matters for TaskInstant_WAITING state,
			// because the scheduler pays no attention to label or RUNNING or ABSENT
			// tasks.
			if t == reconciler.TaskInstant_WAITING {
				if provisionableLabels, err = getProvisionableLabels(n); err != nil {
					logging.Warningf(ctx, err.Error())
					sp.Reconciler.TaskError(n.Task.Id, err.Error())
					continue
				}

				if accountID, err = getAccountID(n); err != nil {
					logging.Warningf(ctx, err.Error())
					sp.Reconciler.TaskError(n.Task.Id, err.Error())
					continue
				}
			}

			// TODO(akeshet): Validate that new tasks have dimensions that match the
			// worker pool dimensions for this scheduler pool.
			update := &reconciler.TaskInstant{
				AccountId: accountID,
				// TODO(akeshet): implement me properly. This should be a separate field
				// of the task state, not the notification time.
				EnqueueTime:         n.Time,
				ProvisionableLabels: provisionableLabels,
				RequestId:           n.Task.Id,
				Time:                n.Time,
				State:               t,
				WorkerId:            n.Task.BotId,
			}
			if err := sp.Reconciler.Notify(ctx, sp.Scheduler, update); err != nil {
				sp.Reconciler.TaskError(n.Task.Id, err.Error())
				logging.Warningf(ctx, err.Error())
				continue
			}
			logging.Debugf(ctx, "Scheduler with id %s successfully applied task update %+v", r.SchedulerId, update)
		}
		logState(ctx, sp.Scheduler.State)
		return entities.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, doNotify, nil); err != nil {
		return nil, err
	}
	return &swarming.NotifyTasksResponse{}, nil
}

// getProvisionableLabels determines the provisionable labels for a given task,
// based on the dimensions of its slices.
func getProvisionableLabels(n *swarming.NotifyTasksItem) ([]string, error) {
	switch len(n.Task.Slices) {
	case 1:
		return []string{}, nil
	case 2:
		s1 := stringset.NewFromSlice(n.Task.Slices[0].Dimensions...)
		s2 := stringset.NewFromSlice(n.Task.Slices[1].Dimensions...)
		// s2 must be a subset of s1 (i.e. the first slice must be more specific about dimensions than the second one)
		// otherwise this is an error.
		if flaws := s2.Difference(s1); flaws.Len() != 0 {
			return nil, errors.Errorf("Invalid slice dimensions; task's 2nd slice dimensions are not a subset of 1st slice dimensions.")
		}

		var provisionable sort.StringSlice
		provisionable = s1.Difference(s2).ToSlice()
		provisionable.Sort()
		return provisionable, nil
	default:
		return nil, errors.Errorf("Invalid slice count %d; quotascheduler only supports 1-slice or 2-slice tasks.", len(n.Task.Slices))
	}
}

// getAccountID determines the account id for a given task, based on its tags.
func getAccountID(n *swarming.NotifyTasksItem) (string, error) {
	m := strpair.ParseMap(n.Task.Tags)
	accounts := m[AccountIDTagKey]
	switch len(accounts) {
	case 0:
		return "", nil
	case 1:
		return accounts[0], nil
	default:
		return "", errors.Errorf("Too many account tags.")
	}
}

func toTaskInstantState(s swarming.TaskState) (reconciler.TaskInstant_State, bool) {
	// These cases appear in the same order as they are defined in swarming/proto/tasks.proto
	// If you add any cases here, please preserve their in-order appearance.
	switch s {
	case swarming.TaskState_RUNNING:
		return reconciler.TaskInstant_RUNNING, true
	case swarming.TaskState_PENDING:
		return reconciler.TaskInstant_WAITING, true
	// The following states all translate to "ABSENT", because they are all equivalent
	// to the task being neither running nor waiting.
	case swarming.TaskState_EXPIRED:
		fallthrough
	case swarming.TaskState_TIMED_OUT:
		fallthrough
	case swarming.TaskState_BOT_DIED:
		fallthrough
	case swarming.TaskState_CANCELED:
		fallthrough
	case swarming.TaskState_COMPLETED:
		fallthrough
	case swarming.TaskState_KILLED:
		fallthrough
	case swarming.TaskState_NO_RESOURCE:
		return reconciler.TaskInstant_ABSENT, true

	// Invalid state.
	default:
		return reconciler.TaskInstant_NULL, false
	}
}

func logState(ctx context.Context, s *scheduler.State) {
	logging.Debugf(ctx, "Scheduler has %d queued tasks, %d workers.", len(s.QueuedRequests), len(s.Workers))
}
