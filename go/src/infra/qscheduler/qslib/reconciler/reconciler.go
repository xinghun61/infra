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

// Package reconciler implements logic necessary to reconcile qslib API calls
// with a quotascheduler state. This is the main public interface for  qslib
// should use.
//
// reconciler provides a State struct with the following principle methods:
//
//  - AssignTasks: Informs the quotascheduler that the given workers
//    are idle, and assigns them new tasks.
//  - Cancellations: Determine which workers should have their currently
//    running tasks aborted.
//  - Notify: Informs the quotascheduler of task state changes, in order to
//    enqueue new tasks in the scheduler or acknowledge that scheduler
//    assignments have been completed.
//
// Not yet implemented methods:
//  - UpdateConfig: Informs quotascheduler of a new configuration, (for
//    instance, containing new account policies).
package reconciler

import (
	"fmt"
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/task"
)

// WorkerQueue represents the queue of qscheduler operations that are pending
// for a given worker.
//
// At present, the queue of operations for a worker can be at most 2 elements
// in length, and consist of either:
// - An Abort Job operation followed by an Assign Job operation.
// - An Assign Job operation.
//
// Therefore, instead of representing this as a list of operations, it is
// convenient to flatten this queue into a single object.
//
// TODO: Turn this into a proto, because it will need to get serialized.
type WorkerQueue struct {
	// EnqueueTime is the time at which these operations were enqueued.
	EnqueueTime time.Time

	// TaskToAssign is the task request that should be assigned to this worker.
	TaskToAssign string

	// TaskToAbort indicates the task request id that should be aborted on this worker.
	//
	// Empty string "" indicates that there is nothing to abort.
	TaskToAbort string
}

// Config represents configuration options for a reconciler.
type Config struct {
	// TODO: Implement me.
	// Include things such as:
	// - ACK timeout for worker aborts.
	// - ACK timeout for worker-task assignments.
}

// State represents a reconciler, which includes its configuration and the
// pending operations that are in-flight and have not been ACK'ed yet.
//
// TODO: Turn this into a proto, because it will need to get serialized.
type State struct {
	Config *Config

	WorkerQueues map[string]*WorkerQueue
}

// New returns a new initialized State instance.
func New() *State {
	return &State{
		Config:       &Config{},
		WorkerQueues: make(map[string]*WorkerQueue),
	}
}

// IdleWorker represents a worker that is idle and wants to have a task assigned.
type IdleWorker struct {
	// ID is the ID of the idle worker.
	ID string

	// ProvisionableLabels is the set of provisionable labels of the idle worker.
	ProvisionableLabels task.LabelSet
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
	UpdateTime(t time.Time) error

	// MarkIdle informs the scheduler that a given worker is idle, with
	// given labels.
	MarkIdle(id string, labels task.LabelSet)

	// RunOnce runs through one round of the scheduling algorithm, and determines
	// and returns work assignments.
	RunOnce() []*scheduler.Assignment

	// AddRequest adds a task request to the queue.
	AddRequest(id string, request *task.Request)
}

// AssignTasks accepts a slice of idle workers, and returns tasks to be assigned
// to those workers (if there are tasks available).
func (state *State) AssignTasks(s Scheduler, workers []*IdleWorker, t time.Time) []Assignment {
	// Step 1: Update scheduler time.
	s.UpdateTime(t)

	// Step 2: Determine which of the supplied workers should be newly marked as
	// idle (because they don't have anything already enqueued). Mark these as idle.
	for _, w := range workers {
		if q := state.WorkerQueues[w.ID]; q == nil {
			s.MarkIdle(w.ID, w.ProvisionableLabels)
		}
	}

	// Step 3: Call scheduler, and update worker queues based on assignments
	// that it yielded.
	newAssignments := s.RunOnce()
	for _, a := range newAssignments {
		if a.TaskToAbort != "" && a.Type != scheduler.Assignment_PREEMPT_WORKER {
			panic(fmt.Sprintf("Received a non-preempt assignment specifing a task to abort %s.", a.TaskToAbort))
		}
		// TODO(akeshet): Log if there was a previous WorkerQueue that we are
		// overwriting.
		state.WorkerQueues[a.WorkerId] = &WorkerQueue{
			EnqueueTime:  tutils.Timestamp(a.Time),
			TaskToAssign: a.RequestId,
			TaskToAbort:  a.TaskToAbort,
		}
	}

	// Step 4: Yield from worker queues.
	assignments := make([]Assignment, 0, len(workers))
	for _, w := range workers {
		if q, ok := state.WorkerQueues[w.ID]; ok {
			assignments = append(assignments, Assignment{RequestID: q.TaskToAssign, WorkerID: w.ID})
			// TODO: If q was a preempt-type assignment, then turn it into assign_idle
			// type assignment now (as the worker already became idle) and log that
			// we no longer need to abort the previous task.
		}
	}

	return assignments
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
func (state *State) Cancellations() []Cancellation {
	// TODO(akeshet): Implement me.
	return nil
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
func (state *State) Notify(s Scheduler, updates ...*TaskUpdate) error {
	// TODO: Determine whether updates should be time-order sorted, and if so
	// whether to do that sorting here or to require if from the caller.

	for _, u := range updates {
		switch u.Type {
		// TODO(akeshet): Add a default case for unhandled types.
		case TaskUpdate_NEW:
			// TODO(akeshet): Handle new tasks that are already running on a worker,
			// likely by having AddRequest return an error.
			s.AddRequest(
				u.RequestId,
				&task.Request{
					AccountId: u.AccountId,
					// TODO(akeshet): Clarify whether u.Time corresponds to the pubsub time,
					// or the enqueue time of the task. If the former, add a field
					// to TaskUpdate to encode the enqueue time.
					// We probably want this to mean the enqueue time (created_ts).
					EnqueueTime: u.Time,
					Labels:      u.ProvisionableLabels,
				})

		case TaskUpdate_ASSIGNED:
			// TODO(akeshet): Implement me.
		case TaskUpdate_INTERRUPTED:
			// TODO(akeshet): Implement me.
		}
	}

	return nil
}
