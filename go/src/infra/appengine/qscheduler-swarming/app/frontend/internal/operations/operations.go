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

package operations

import (
	"context"
	"fmt"
	"sort"

	"infra/appengine/qscheduler-swarming/app/entities"
	swarming "infra/swarming"

	"github.com/pkg/errors"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/logging"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// AccountIDTagKey is the key used in Task tags to specify which quotascheduler
// account the task should be charged to.
const AccountIDTagKey = "qs_account"

// Operation is the type for functions that examine and mutate a state.
type Operation func(ctx context.Context, state *entities.QSchedulerState) error

// AssignResult holds an eventual result or error from an AssignTasks operation.
type AssignResult struct {
	Response *swarming.AssignTasksResponse
	Error    error
}

// SetError nulls out any Response and sets the given error.
func (a *AssignResult) SetError(err error) {
	a.Response = nil
	a.Error = err
}

// AssignTasks returns an operation that will perform the given Assign request.
//
// The result object will have the operation response stored in it after
// the operation has run.
func AssignTasks(r *swarming.AssignTasksRequest) (Operation, *AssignResult) {
	var response AssignResult
	return func(ctx context.Context, state *entities.QSchedulerState) (err error) {
		defer func() {
			response.Error = err
		}()
		idles := make([]*reconciler.IdleWorker, len(r.IdleBots))
		for i, v := range r.IdleBots {
			s := stringset.NewFromSlice(v.Dimensions...)
			if !s.HasAll(state.Config.Labels...) {
				return status.Errorf(codes.InvalidArgument, "bot with id %s does not have all scheduler dimensions", v.BotId)
			}
			idles[i] = &reconciler.IdleWorker{
				ID:     scheduler.WorkerID(v.BotId),
				Labels: stringset.NewFromSlice(v.Dimensions...),
			}
		}

		schedulerAssignments, err := state.Reconciler.AssignTasks(ctx, state.Scheduler, tutils.Timestamp(r.Time), idles...)
		if err != nil {
			return err
		}

		assignments := make([]*swarming.TaskAssignment, len(schedulerAssignments))
		for i, v := range schedulerAssignments {
			slice := int32(0)
			if v.ProvisionRequired {
				slice = 1
			}
			assignments[i] = &swarming.TaskAssignment{
				BotId:       string(v.WorkerID),
				TaskId:      string(v.RequestID),
				SliceNumber: slice,
			}
		}

		response.Response = &swarming.AssignTasksResponse{Assignments: assignments}
		return nil
	}, &response
}

// NotifyResult holds an eventual result or error from a NotifyTasks operation.
type NotifyResult struct {
	Response *swarming.NotifyTasksResponse
	Error    error
}

// SetError nulls out any Response and sets the given error.
func (a *NotifyResult) SetError(err error) {
	a.Response = nil
	a.Error = err
}

// NotifyTasks returns an operation that will perform the given Notify request,
// and result object that will get the results after the operation is run.
func NotifyTasks(r *swarming.NotifyTasksRequest) (Operation, *NotifyResult) {
	var response NotifyResult
	return func(ctx context.Context, sp *entities.QSchedulerState) (err error) {
		defer func() {
			response.Error = err
		}()

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
			var err error
			// ProvisionableLabels attribute only matters for TaskInstant_WAITING state,
			// because the scheduler pays no attention to label or RUNNING or ABSENT
			// tasks.
			if t == reconciler.TaskInstant_WAITING {
				if provisionableLabels, err = ProvisionableLabels(n); err != nil {
					logging.Warningf(ctx, err.Error())
					sp.Reconciler.TaskError(n.Task.Id, err.Error())
					continue
				}

				if accountID, err = GetAccountID(n); err != nil {
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
		response.Response = &swarming.NotifyTasksResponse{}
		return nil
	}, &response
}

// ProvisionableLabels determines the provisionable labels for a given task,
// based on the dimensions of its slices.
func ProvisionableLabels(n *swarming.NotifyTasksItem) ([]string, error) {
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

// GetAccountID determines the account id for a given task, based on its tags.
func GetAccountID(n *swarming.NotifyTasksItem) (string, error) {
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
	cInt := int(s) &^ int(swarming.TaskStateCategory_TASK_STATE_MASK)
	category := swarming.TaskStateCategory(cInt)

	// These category cases occur in the same order as they are defined in
	// swarming.proto. Please preserve that when adding new cases.
	switch category {
	case swarming.TaskStateCategory_CATEGORY_PENDING:
		return reconciler.TaskInstant_WAITING, true
	case swarming.TaskStateCategory_CATEGORY_RUNNING:
		return reconciler.TaskInstant_RUNNING, true
	// The following categories all translate to "ABSENT", because they are all
	// equivalent to the task being neither running nor waiting.
	case swarming.TaskStateCategory_CATEGORY_TRANSIENT_DONE,
		swarming.TaskStateCategory_CATEGORY_EXECUTION_DONE,
		swarming.TaskStateCategory_CATEGORY_NEVER_RAN_DONE:
		return reconciler.TaskInstant_ABSENT, true

	// Invalid state.
	default:
		return reconciler.TaskInstant_NULL, false
	}
}
