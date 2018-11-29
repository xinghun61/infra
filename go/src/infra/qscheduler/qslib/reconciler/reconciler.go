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
)

// New returns a new initialized State instance.
func New() *State {
	return &State{
		WorkerQueues: make(map[string]*WorkerQueue),
	}
}

// IdleWorker represents a worker that is idle and wants to have a task assigned.
type IdleWorker struct {
	// ID is the ID of the idle worker.
	ID string

	// ProvisionableLabels is the set of provisionable labels of the idle worker.
	ProvisionableLabels scheduler.LabelSet
}

// Assignment represents a scheduler-initated operation to assign a task to a worker.
type Assignment struct {
	// WorkerID is the ID the worker that is being assigned a task.
	WorkerID string

	// RequestID is the ID of the task request that is being assigned.
	RequestID string
}

// Scheduler is the interface with which reconciler interacts with a scheduler.
// One implementation of this interface (the quotascheduler) is provided
// by qslib/scheduler.Scheduler.
type Scheduler interface {
	// UpdateTime informs the scheduler of the current time.
	UpdateTime(ctx context.Context, t time.Time) error

	// MarkIdle informs the scheduler that a given worker is idle, with
	// given labels.
	MarkIdle(ctx context.Context, workerID string, labels scheduler.LabelSet, t time.Time) error

	// RunOnce runs through one round of the scheduling algorithm, and determines
	// and returns work assignments.
	RunOnce(ctx context.Context) ([]*scheduler.Assignment, error)

	// AddRequest adds a task request to the queue.
	AddRequest(ctx context.Context, requestID string, request *scheduler.TaskRequest, t time.Time) error

	// IsAssigned returns whether the given request is currently assigned to the
	// given worker.
	IsAssigned(requestID string, workerID string) bool

	// NotifyRequest informs the scheduler authoritatively that the given request
	// was running on the given worker (or was idle, for workerID = "") at the
	// given time.
	//
	// Supplied requestID must not be "".
	//
	// Note: calls to NotifyRequest come from task update pubsub messages from swarming.
	NotifyRequest(ctx context.Context, requestID string, workerID string, t time.Time) error

	// AbortRequest informs the scheduler authoritatively that the given request
	// is stopped (not running on a worker, and not in the queue) at the given time.
	//
	// Supplied requestID must not be "".
	AbortRequest(ctx context.Context, requestID string, t time.Time) error
}

// AssignTasks accepts one or more idle workers, and returns tasks to be assigned
// to those workers (if there are tasks available).
func (state *State) AssignTasks(ctx context.Context, s Scheduler, t time.Time, workers ...*IdleWorker) ([]Assignment, error) {
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
		q, ok := state.WorkerQueues[wid]
		if !ok || !s.IsAssigned(q.TaskToAssign, wid) {
			if err := s.MarkIdle(ctx, wid, w.ProvisionableLabels, t); err != nil {
				return nil, err
			}
			delete(state.WorkerQueues, wid)
		}
	}

	// Call scheduler, and update worker queues based on assignments that it
	// yielded.
	newAssignments, err := s.RunOnce(ctx)
	if err != nil {
		return nil, err
	}

	for _, a := range newAssignments {
		if a.TaskToAbort != "" && a.Type != scheduler.Assignment_PREEMPT_WORKER {
			panic(fmt.Sprintf("Received a non-preempt assignment specifing a task to abort %s.", a.TaskToAbort))
		}
		// TODO(akeshet): Log if there was a previous WorkerQueue that we are
		// overwriting.
		state.WorkerQueues[a.WorkerId] = &WorkerQueue{
			EnqueueTime:  a.Time,
			TaskToAssign: a.RequestId,
			TaskToAbort:  a.TaskToAbort,
		}
	}

	// Yield from worker queues.
	assignments := make([]Assignment, 0, len(workers))
	for _, w := range workers {
		if q, ok := state.WorkerQueues[w.ID]; ok {
			assignments = append(assignments, Assignment{RequestID: q.TaskToAssign, WorkerID: w.ID})
			// TODO: If q was a preempt-type assignment, then turn it into assign_idle
			// type assignment now (as the worker already became idle) and log that
			// we no longer need to abort the previous task.
		}
	}

	return assignments, nil
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
}

// Cancellations returns the set of workers and tasks that should be cancelled.
func (state *State) Cancellations(ctx context.Context) []Cancellation {
	state.ensureMaps()
	c := make([]Cancellation, 0, len(state.WorkerQueues))
	for wid, q := range state.WorkerQueues {
		if q.TaskToAbort != "" {
			c = append(c, Cancellation{RequestID: q.TaskToAbort, WorkerID: wid})
		}
	}
	return c
}

// Notify informs the quotascheduler about task state changes.
//
// Task state changes include: creation of new tasks, assignment of task to
// worker, cancellation of a task.
//
// Notify must be called in order to acknowledge that previously returned
// scheduler operations have been completed (otherwise: subsequent AssignTasks or
// Cancellations will return stale data until internal timeouts within reconciler
// expire).
func (state *State) Notify(ctx context.Context, s Scheduler, updates ...*TaskUpdate) error {
	state.ensureMaps()
	for _, update := range updates {
		switch update.Type {
		case TaskUpdate_NEW:
			req := scheduler.NewRequest(update.AccountId, update.ProvisionableLabels,
				tutils.Timestamp(update.EnqueueTime))
			s.AddRequest(ctx, update.RequestId, req, tutils.Timestamp(update.Time))

		case TaskUpdate_ASSIGNED:
			wid := update.WorkerId
			rid := update.RequestId
			updateTime := tutils.Timestamp(update.Time)
			// This NotifyRequest call ensures scheduler state consistency with
			// the latest update.
			s.NotifyRequest(ctx, rid, wid, updateTime)
			if q, ok := state.WorkerQueues[wid]; ok {
				if !updateTime.Before(tutils.Timestamp(q.EnqueueTime)) {
					delete(state.WorkerQueues, wid)
					// TODO(akeshet): Log or handle "unexpected request on worker" here.
				} else {
					// TODO(akeshet): Consider whether we should delete from workerqueue
					// here for non-forward updates that are still a (wid, rid) match
					// for the expected assignment.
				}
			}

		case TaskUpdate_INTERRUPTED:
			rid := update.RequestId
			updateTime := tutils.Timestamp(update.Time)
			// This NotifyRequest call ensures scheduler state consistency with
			// the latest update.
			s.NotifyRequest(ctx, rid, "", updateTime)
			// TODO(akeshet): Add an inverse map from aborting request -> previous
			// worker to avoid the need for this iteration through all workers.
			for wid, q := range state.WorkerQueues {
				if q.TaskToAbort == rid && tutils.Timestamp(q.EnqueueTime).Before(updateTime) {
					delete(state.WorkerQueues, wid)
				}
			}
		}
	}
	return nil
}

// ensureMaps initializes any nil maps in reconciler.
//
// This is necessary because protobuf deserialization of an empty map returns a nil map.
func (state *State) ensureMaps() {
	if state.WorkerQueues == nil {
		state.WorkerQueues = make(map[string]*WorkerQueue)
	}
}
