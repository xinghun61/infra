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

// Package reconciler implements logic necessary to reconcile API calls
// (Update, Reap, etc) to qslib with a quotascheduler state. This is the
// main interface that external clients to qslib should use.
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

// GetCancellations returns the set of workers and tasks that should be cancelled.
func (state *State) GetCancellations(t time.Time) []Cancellation {
	// TODO: implement me
	return nil
}

// TaskUpdate represents a change in the state of an existing task, or the
// creation of a new task.
type TaskUpdate struct {
	// TODO: Implement me.
	// Should specify things like:
	// - task id
	// - task state (New, Assigned, Cancelled)
	// - worker id (if state is Assigned)
	Time time.Time
}

// UpdateTasks is called to inform a quotascheduler about task state changes
// (creation of new tasks, assignment of task to worker, cancellation of a task).
// These updates must be sent to acknowledge that previously returned
// scheduler operations have been completed (otherwise, future calls to AssignTasks
// or GetCancellations will continue to return their previous results).
func (state *State) UpdateTasks(updates []TaskUpdate) {
	// TODO: Implement me.
}
