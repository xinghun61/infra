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
	"time"

	"github.com/pkg/errors"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
	"infra/swarming"
)

// AccountIDTagKey is the key used in Task tags to specify which quotascheduler
// account the task should be charged to.
const AccountIDTagKey = "qs_account"

// AssignTasks returns an operation that will perform the given Assign requests.
//
// The results slice will have the operation responses stored in it after
// the operation has run, as parallel entries to the slice of requests.
func AssignTasks(r []*swarming.AssignTasksRequest) (types.Operation, []*swarming.AssignTasksResponse) {
	response := make([]*swarming.AssignTasksResponse, len(r))
	// Make a copy of input slice and use that below, in case the slice is
	// mutated prior to callback of returned operation.
	temp := make([]*swarming.AssignTasksRequest, len(r))
	copy(temp, r)
	r = temp
	return func(ctx context.Context, state *types.QScheduler, events scheduler.EventSink) {
		var idles []*reconciler.IdleWorker
		timestamp := time.Unix(0, 0)
		for _, req := range r {
			for _, v := range req.IdleBots {
				idles = append(idles, &reconciler.IdleWorker{
					ID:     scheduler.WorkerID(v.BotId),
					Labels: stringset.NewFromSlice(v.Dimensions...),
				})
			}
			if t := tutils.Timestamp(req.Time); t.After(timestamp) {
				timestamp = t
			}
		}

		schedulerAssignments := state.Reconciler.AssignTasks(ctx, state.Scheduler, timestamp, events, idles...)

		assignmentsByBot := make(map[scheduler.WorkerID]*swarming.TaskAssignment, len(schedulerAssignments))
		for _, v := range schedulerAssignments {
			slice := int32(0)
			if v.ProvisionRequired {
				slice = 1
			}
			// Note: WorkerID is unique for every item in the schedulerAssignments
			// list, so don't bother checking if we're overwriting an entry.
			assignmentsByBot[v.WorkerID] = &swarming.TaskAssignment{
				BotId:       string(v.WorkerID),
				TaskId:      string(v.RequestID),
				SliceNumber: slice,
			}
		}

		for i, req := range r {
			var assignments []*swarming.TaskAssignment
			for _, idle := range req.IdleBots {
				if a, ok := assignmentsByBot[scheduler.WorkerID(idle.BotId)]; ok {
					assignments = append(assignments, a)
				}
			}
			response[i] = &swarming.AssignTasksResponse{Assignments: assignments}
		}
	}, response
}

// NotifyTasks returns an operation that will perform the given Notify request,
// and result object that will get the results after the operation is run.
func NotifyTasks(r *swarming.NotifyTasksRequest) (types.Operation, *swarming.NotifyTasksResponse) {
	var response swarming.NotifyTasksResponse
	return func(ctx context.Context, sp *types.QScheduler, events scheduler.EventSink) {
		if r.IsCallback {
			events = events.WithFields(true)
		}

		for _, n := range r.Notifications {
			var t taskState
			var ok bool
			if t, ok = translateTaskState(n.Task.State); !ok {
				err := errors.Errorf("Invalid notification with unhandled state %s.", n.Task.State)
				logging.Warningf(ctx, err.Error())
				sp.Reconciler.AddTaskError(scheduler.RequestID(n.Task.Id), err)
				continue
			}

			switch t {
			case taskStateAbsent:
				r := &reconciler.TaskAbsentRequest{RequestID: scheduler.RequestID(n.Task.Id), Time: tutils.Timestamp(n.Time)}
				sp.Reconciler.NotifyTaskAbsent(ctx, sp.Scheduler, events, r)
			case taskStateRunning:
				r := &reconciler.TaskRunningRequest{
					RequestID: scheduler.RequestID(n.Task.Id),
					Time:      tutils.Timestamp(n.Time),
					WorkerID:  scheduler.WorkerID(n.Task.BotId),
				}
				sp.Reconciler.NotifyTaskRunning(ctx, sp.Scheduler, events, r)
			case taskStateWaiting:
				if err := notifyTaskWaiting(ctx, sp, events, n); err != nil {
					sp.Reconciler.AddTaskError(scheduler.RequestID(n.Task.Id), err)
					logging.Warningf(ctx, err.Error())
				}
			default:
				e := errors.Errorf("invalid update type %d", t)
				logging.Warningf(ctx, e.Error())
				sp.Reconciler.AddTaskError(scheduler.RequestID(n.Task.Id), e)
			}
		}
		response = swarming.NotifyTasksResponse{}
	}, &response
}

func notifyTaskWaiting(ctx context.Context, sp *types.QScheduler, events scheduler.EventSink, n *swarming.NotifyTasksItem) error {
	var provisionableLabels []string
	var baseLabels []string
	var accountID string
	labels, err := computeLabels(n)
	if err != nil {
		return err
	}
	provisionableLabels = labels.provisionable
	baseLabels = labels.base

	if accountID, err = GetAccountID(n); err != nil {
		return err
	}
	r := &reconciler.TaskWaitingRequest{
		AccountID:           scheduler.AccountID(accountID),
		BaseLabels:          stringset.NewFromSlice(baseLabels...),
		EnqueueTime:         tutils.Timestamp(n.Task.EnqueuedTime),
		ProvisionableLabels: stringset.NewFromSlice(provisionableLabels...),
		RequestID:           scheduler.RequestID(n.Task.Id),
		Tags:                n.Task.Tags,
		Time:                tutils.Timestamp(n.Time),
	}
	sp.Reconciler.NotifyTaskWaiting(ctx, sp.Scheduler, events, r)

	return nil
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

type taskState int

const (
	taskStateUnknown taskState = iota
	taskStateWaiting
	taskStateRunning
	taskStateAbsent
)

func translateTaskState(s swarming.TaskState) (taskState, bool) {
	cInt := int(s) &^ int(swarming.TaskStateCategory_TASK_STATE_MASK)
	category := swarming.TaskStateCategory(cInt)

	// These category cases occur in the same order as they are defined in
	// swarming.proto. Please preserve that when adding new cases.
	switch category {
	case swarming.TaskStateCategory_CATEGORY_PENDING:
		return taskStateWaiting, true
	case swarming.TaskStateCategory_CATEGORY_RUNNING:
		return taskStateRunning, true
	// The following categories all translate to "ABSENT", because they are all
	// equivalent to the task being neither running nor waiting.
	case swarming.TaskStateCategory_CATEGORY_TRANSIENT_DONE,
		swarming.TaskStateCategory_CATEGORY_EXECUTION_DONE,
		swarming.TaskStateCategory_CATEGORY_NEVER_RAN_DONE:
		return taskStateAbsent, true

	// Invalid state.
	default:
		return taskStateUnknown, false
	}
}

// labels represents the computed labels for a task.
type labels struct {
	provisionable []string
	base          []string
}
