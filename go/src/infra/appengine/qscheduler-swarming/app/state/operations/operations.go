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

	swarming "infra/swarming"

	"github.com/pkg/errors"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// AccountIDTagKey is the key used in Task tags to specify which quotascheduler
// account the task should be charged to.
const AccountIDTagKey = "qs_account"

// AssignTasks returns an operation that will perform the given Assign request.
//
// The result object will have the operation response stored in it after
// the operation has run.
func AssignTasks(r *swarming.AssignTasksRequest) (types.Operation, *swarming.AssignTasksResponse) {
	var response swarming.AssignTasksResponse
	return func(ctx context.Context, state *types.QScheduler, metrics scheduler.MetricsSink) (err error) {
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

		schedulerAssignments, err := state.Reconciler.AssignTasks(ctx, state.Scheduler, tutils.Timestamp(r.Time), metrics, idles...)
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

		response = swarming.AssignTasksResponse{Assignments: assignments}
		return nil
	}, &response
}

// NotifyTasks returns an operation that will perform the given Notify request,
// and result object that will get the results after the operation is run.
func NotifyTasks(r *swarming.NotifyTasksRequest) (types.Operation, *swarming.NotifyTasksResponse) {
	var response swarming.NotifyTasksResponse
	return func(ctx context.Context, sp *types.QScheduler, metrics scheduler.MetricsSink) (err error) {
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
			var baseLabels []string
			var accountID string
			// ProvisionableLabels and BaseLabels attribute only matter for
			// TaskInstant_WAITING state because the scheduler pays no attention
			// to labels of RUNNING or ABSENT tasks.
			//
			// The same is true of AccountID
			if t == reconciler.TaskInstant_WAITING {
				labels, err := computeLabels(n)
				if err != nil {
					logging.Warningf(ctx, err.Error())
					sp.Reconciler.TaskError(n.Task.Id, err.Error())
					continue
				}
				provisionableLabels = labels.provisionable
				baseLabels = labels.base

				s := stringset.NewFromSlice(baseLabels...)
				if !s.HasAll(sp.Config.Labels...) {
					msg := fmt.Sprintf("task with base dimensions %s does not contain all of scheduler dimensions %s", baseLabels, sp.Config.Labels)
					logging.Warningf(ctx, msg)
					sp.Reconciler.TaskError(n.Task.Id, msg)
					continue
				}

				if accountID, err = GetAccountID(n); err != nil {
					logging.Warningf(ctx, err.Error())
					sp.Reconciler.TaskError(n.Task.Id, err.Error())
					continue
				}
			}

			update := &reconciler.TaskInstant{
				AccountId:           accountID,
				EnqueueTime:         n.Task.EnqueuedTime,
				ProvisionableLabels: provisionableLabels,
				BaseLabels:          baseLabels,
				RequestId:           n.Task.Id,
				Time:                n.Time,
				State:               t,
				WorkerId:            n.Task.BotId,
			}

			var err error
			switch update.State {
			case reconciler.TaskInstant_ABSENT:
				err = sp.Reconciler.NotifyTaskAbsent(ctx, sp.Scheduler, metrics, update)
			case reconciler.TaskInstant_RUNNING:
				err = sp.Reconciler.NotifyTaskRunning(ctx, sp.Scheduler, metrics, update)
			case reconciler.TaskInstant_WAITING:
				err = sp.Reconciler.NotifyTaskWaiting(ctx, sp.Scheduler, metrics, update)
			default:
				panic("Invalid update type.")
			}
			if err != nil {
				sp.Reconciler.TaskError(n.Task.Id, err.Error())
				logging.Warningf(ctx, err.Error())
				continue
			}
			logging.Debugf(ctx, "Scheduler with id %s successfully applied task update %+v", r.SchedulerId, update)
		}
		response = swarming.NotifyTasksResponse{}
		return nil
	}, &response
}

// computeLabels determines the labels for a given task.
func computeLabels(n *swarming.NotifyTasksItem) (*labels, error) {
	slices := n.Task.Slices
	switch len(slices) {
	case 1:
		return &labels{base: slices[0].Dimensions}, nil
	case 2:
		s1 := stringset.NewFromSlice(slices[0].Dimensions...)
		s2 := stringset.NewFromSlice(slices[1].Dimensions...)
		// s2 must be a subset of s1 (i.e. the first slice must be more specific
		// about dimensions than the second one).
		if flaws := s2.Difference(s1); flaws.Len() != 0 {
			return nil, errors.Errorf("Invalid slice dimensions; task's 2nd slice dimensions are not a subset of 1st slice dimensions.")
		}

		provisionable := s1.Difference(s2).ToSlice()
		base := slices[1].Dimensions
		return &labels{provisionable: provisionable, base: base}, nil
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

// labels represents the computed labels for a task.
type labels struct {
	provisionable []string
	base          []string
}
