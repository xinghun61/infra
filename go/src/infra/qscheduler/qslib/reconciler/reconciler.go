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

/*
Package reconciler provides a wrapper around a global state scheduler to be used
by a per-worker pulling dispatcher. TODO(akeshet): Rename this package to
something more descriptive but still succinct. Options include: broker,
distributor, mediator, etc.

The primary scheduler.Scheduler implementation intended to be used by reconciler
is the quotascheduler algorithm as implemented in qslib/scheduler. The primary
dispatcher client is intended to be swarming.

The reconciler tracks the queue of actions for workers that have pending
actions (both those in the most recent pull call from client, and those not).
For each worker, reconciler holds actions in the queue until they are acknowledged,
and orchestrates task preemption.
*/
package reconciler

import (
	"context"
	"fmt"
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
)

// New returns a new initialized State instance.
func New() *State {
	return &State{
		WorkerQueues: make(map[string]*WorkerQueue),
	}
}

// WorkerID is a type alias for WorkerID
type WorkerID = scheduler.WorkerID

// RequestID is a type alias for RequestID
type RequestID = scheduler.RequestID

// AccountID is a type alias for AccountID
type AccountID = scheduler.AccountID

// IdleWorker represents a worker that is idle and wants to have a task assigned.
type IdleWorker struct {
	// ID is the ID of the idle worker.
	ID WorkerID

	// Labels is the set of labels of the idle worker.
	Labels stringset.Set
}

// Assignment represents a scheduler-initated operation to assign a task to a worker.
type Assignment struct {
	// WorkerID is the ID the worker that is being assigned a task.
	WorkerID WorkerID

	// RequestID is the ID of the task request that is being assigned.
	RequestID RequestID

	// ProvisionRequired indicates whether the worker needs to be provisioned (in other
	// words, it is true if the worker does not possess the request's provisionable
	// labels.)
	ProvisionRequired bool
}

// AssignTasks accepts one or more idle workers, and returns tasks to be assigned
// to those workers (if there are tasks available).
func (state *State) AssignTasks(ctx context.Context, s *scheduler.Scheduler, t time.Time, metrics scheduler.MetricsSink, workers ...*IdleWorker) ([]Assignment, error) {
	state.ensureMaps()
	s.UpdateTime(ctx, t)

	// Determine which of the supplied workers should be newly marked as
	// idle. This should be done if either:
	//  - The reconciler doesn't have anything queued for that worker.
	//  - The reconciler has a task queued for that worker, but it is inconsistent
	//    with the scheduler's opinion. This means we've received some previous
	//    notify call with an unexpected worker for a given request. We defer
	//    to the scheduler's state, which has its own NotifyRequest logic that
	//    correctly handles this and accounts for out-of-order updates and other
	//    subtleties.
	for _, w := range workers {
		wid := w.ID
		q, ok := state.WorkerQueues[string(wid)]
		if !ok || !s.IsAssigned(RequestID(q.TaskToAssign), wid) {
			if err := s.MarkIdle(ctx, wid, w.Labels, t, metrics); err != nil {
				return nil, err
			}
			delete(state.WorkerQueues, string(wid))
		}
	}

	// Call scheduler, and update worker queues based on assignments that it
	// yielded.
	newAssignments, err := s.RunOnce(ctx, metrics)
	if err != nil {
		return nil, err
	}

	for _, a := range newAssignments {
		if a.TaskToAbort != "" && a.Type != scheduler.AssignmentPreemptWorker {
			panic(fmt.Sprintf("Received a non-preempt assignment specifing a task to abort %s.", a.TaskToAbort))
		}
		// TODO(akeshet): Log if there was a previous WorkerQueue that we are
		// overwriting.
		state.WorkerQueues[string(a.WorkerID)] = &WorkerQueue{
			EnqueueTime:  tutils.TimestampProto(a.Time),
			TaskToAssign: string(a.RequestID),
			TaskToAbort:  string(a.TaskToAbort),
		}
	}

	// Yield from worker queues.
	assignments := make([]Assignment, 0, len(workers))
	for _, w := range workers {
		if q, ok := state.WorkerQueues[string(w.ID)]; ok {
			// Note: We determine whether provision is needed here rather than
			// using the determination used within the Scheduler, because we have the
			// newest info about worker dimensions here.
			r, _ := s.GetRequest(RequestID(q.TaskToAssign))
			provisionRequired := !w.Labels.Contains(r.ProvisionableLabels)

			assignments = append(assignments, Assignment{
				RequestID:         RequestID(q.TaskToAssign),
				WorkerID:          w.ID,
				ProvisionRequired: provisionRequired,
			})
			// TODO: If q was a preempt-type assignment, then turn it into assign_idle
			// type assignment now (as the worker already became idle) and log that
			// we no longer need to abort the previous task.
		}
	}

	return assignments, nil
}

// TaskError marks a given task as having failed due to an error, and in need of cancellation.
func (state *State) TaskError(requestID string, err string) {
	state.ensureMaps()
	state.TaskErrors[requestID] = err
}

// Cancellation represents a scheduler-initated operation to cancel a task on a worker.
// The worker should be aborted if and only if it is currently running the given task.
//
//TODO: Consider unifying this with Assignment, since it is in fact the same content.
type Cancellation struct {
	// WorkerID is the id the worker where we should cancel a task.
	WorkerID string

	// RequestID is the id of the task that we should request.
	RequestID string

	// ErrorMessage is a description of the error that caused the task to be
	// cancelled, if it was cancelled due to error.
	ErrorMessage string
}

// Cancellations returns the set of workers and tasks that should be cancelled.
func (state *State) Cancellations(ctx context.Context) []Cancellation {
	state.ensureMaps()
	c := make([]Cancellation, 0, len(state.WorkerQueues)+len(state.TaskErrors))
	for wid, q := range state.WorkerQueues {
		if q.TaskToAbort != "" {
			c = append(c, Cancellation{RequestID: q.TaskToAbort, WorkerID: wid})
		}
	}
	for tid, err := range state.TaskErrors {
		c = append(c, Cancellation{RequestID: tid, ErrorMessage: err})
	}
	return c
}

// NotifyTaskWaiting informs the quotascheduler about a waiting task.
func (state *State) NotifyTaskWaiting(ctx context.Context, s *scheduler.Scheduler, metrics scheduler.MetricsSink, update *TaskWaitingRequest) error {
	state.ensureMaps()

	if err := s.UpdateTime(ctx, update.Time); err != nil {
		logging.Warningf(ctx, "ignoring UpdateTime error: %s", err.Error())
	}

	req := scheduler.NewTaskRequest(
		update.RequestID,
		update.AccountID,
		update.ProvisionableLabels,
		update.BaseLabels,
		update.EnqueueTime)
	// TODO(akeshet): Handle error from AddRequest.
	s.AddRequest(ctx, req, update.Time, metrics)

	return nil
}

// NotifyTaskRunning informs the quotascheduler about a running task.
func (state *State) NotifyTaskRunning(ctx context.Context, s *scheduler.Scheduler, metrics scheduler.MetricsSink, update *TaskRunningRequest) error {
	state.ensureMaps()

	if err := s.UpdateTime(ctx, update.Time); err != nil {
		logging.Warningf(ctx, "ignoring UpdateTime error: %s", err.Error())
	}

	wid := update.WorkerID
	rid := update.RequestID
	// This NotifyRequest call ensures scheduler state consistency with
	// the latest update.
	s.NotifyRequest(ctx, rid, wid, update.Time, metrics)
	if q, ok := state.WorkerQueues[string(wid)]; ok {
		if !update.Time.Before(tutils.Timestamp(q.EnqueueTime)) {
			delete(state.WorkerQueues, string(wid))
			// TODO(akeshet): Log or handle "unexpected request on worker" here.
		} else {
			// TODO(akeshet): Consider whether we should delete from workerqueue
			// here for non-forward updates that are still a (wid, rid) match
			// for the expected assignment.
		}
	}

	return nil
}

// NotifyTaskAbsent informs the quotascheduler about an absent task.
func (state *State) NotifyTaskAbsent(ctx context.Context, s *scheduler.Scheduler, metrics scheduler.MetricsSink, update *TaskInstant) error {
	state.ensureMaps()
	if update.State != TaskInstant_ABSENT {
		panic("invalid update type")
	}

	rid := RequestID(update.RequestId)
	updateTime := tutils.Timestamp(update.Time)
	s.AbortRequest(ctx, rid, updateTime, metrics)
	// TODO(akeshet): Add an inverse map from aborting request -> previous
	// worker to avoid the need for this iteration through all workers.
	for wid, q := range state.WorkerQueues {
		if q.TaskToAbort == string(rid) && tutils.Timestamp(q.EnqueueTime).Before(updateTime) {
			delete(state.WorkerQueues, wid)
		}
	}
	delete(state.TaskErrors, string(rid))

	return nil
}

// ensureMaps initializes any nil maps in reconciler.
//
// This is necessary because protobuf deserialization of an empty map returns a nil map.
func (state *State) ensureMaps() {
	if state.WorkerQueues == nil {
		state.WorkerQueues = make(map[string]*WorkerQueue)
	}
	if state.TaskErrors == nil {
		state.TaskErrors = make(map[string]string)
	}
}
