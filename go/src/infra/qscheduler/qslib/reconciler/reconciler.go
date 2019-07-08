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

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
)

// WorkerQueueTimeout is the time after which a task will return to the queue
// if it was assigned to a worker but the worker never picked it up.
// TODO(akeshet): Make this a configurable value.
const WorkerQueueTimeout = time.Duration(10) * time.Minute

// New returns a new initialized State instance.
func New() *State {
	return &State{
		proto: &protos.Reconciler{
			WorkerQueues: make(map[string]*protos.WorkerQueue),
		},
	}
}

// NewFromProto returns a new State instance from a proto representation.
func NewFromProto(proto *protos.Reconciler) *State {
	return &State{
		proto: proto,
	}
}

// ToProto converts a reconciler state to proto representation.
func (state *State) ToProto() *protos.Reconciler {
	return state.proto
}

// IdleWorker represents a worker that is idle and wants to have a task assigned.
type IdleWorker struct {
	// ID is the ID of the idle worker.
	ID scheduler.WorkerID

	// Labels is the set of labels of the idle worker.
	Labels stringset.Set
}

// Assignment represents a scheduler-initated operation to assign a task to a worker.
type Assignment struct {
	// WorkerID is the ID the worker that is being assigned a task.
	WorkerID scheduler.WorkerID

	// RequestID is the ID of the task request that is being assigned.
	RequestID scheduler.RequestID

	// ProvisionRequired indicates whether the worker needs to be provisioned (in other
	// words, it is true if the worker does not possess the request's provisionable
	// labels.)
	ProvisionRequired bool
}

// AssignTasks accepts one or more idle workers, and returns tasks to be assigned
// to those workers (if there are tasks available).
func (state *State) AssignTasks(ctx context.Context, s *scheduler.Scheduler, t time.Time, events scheduler.EventSink, workers ...*IdleWorker) []Assignment {
	state.ensureMaps()
	state.timeoutWorkers(ctx, s, t, events)
	s.UpdateTime(ctx, t)

	// Determine which of the supplied workers should be newly marked as
	// idle. This should be done if either:
	//  - The reconciler doesn't have anything queued for that worker.
	//  - The reconciler has a task queued for that worker, but it is inconsistent
	//    with the scheduler's opinion. We defer to the scheduler's state, which
	//    has its own NotifyRequest logic that correctly handles this and accounts
	//    for out-of-order updates and other subtleties.
	for _, w := range workers {
		wid := w.ID
		q, ok := state.proto.WorkerQueues[string(wid)]
		if !ok || !s.IsAssigned(scheduler.RequestID(q.TaskToAssign), wid) {
			s.MarkIdle(ctx, wid, w.Labels, t, events)
			delete(state.proto.WorkerQueues, string(wid))
		}
	}

	// Call scheduler, and update worker queues based on assignments that it
	// yielded.
	newAssignments := s.RunOnce(ctx, events)

	for _, a := range newAssignments {
		if a.TaskToAbort != "" && a.Type != scheduler.AssignmentPreemptWorker {
			panic(fmt.Sprintf("Received a non-preempt assignment specifying a task to abort %s.", a.TaskToAbort))
		}
		new := &protos.WorkerQueue{
			EnqueueTime:  tutils.TimestampProto(a.Time),
			TaskToAssign: string(a.RequestID),
			TaskToAbort:  string(a.TaskToAbort),
		}
		if q, ok := state.proto.WorkerQueues[string(a.WorkerID)]; ok {
			logging.Debugf(ctx, "Clobbering previous WorkerQueue %+v for worker %s with new WorkerQueue %+v", q, a.WorkerID, new)
		}
		state.proto.WorkerQueues[string(a.WorkerID)] = new
	}

	// Yield from worker queues.
	assignments := make([]Assignment, 0, len(workers))
	for _, w := range workers {
		if q, ok := state.proto.WorkerQueues[string(w.ID)]; ok {
			// Note: We determine whether provision is needed here rather than
			// using the determination used within the Scheduler, because we have the
			// newest info about worker dimensions here.
			r, _ := s.GetRequest(scheduler.RequestID(q.TaskToAssign))
			provisionRequired := !w.Labels.Contains(r.ProvisionableLabels)

			assignments = append(assignments, Assignment{
				RequestID:         scheduler.RequestID(q.TaskToAssign),
				WorkerID:          w.ID,
				ProvisionRequired: provisionRequired,
			})
			// TODO: If q was a preempt-type assignment, then turn it into assign_idle
			// type assignment now (as the worker already became idle) and log that
			// we no longer need to abort the previous task.
		}
	}

	return assignments
}

// AddTaskError marks a given task as having failed due to an error, and in need of cancellation.
func (state *State) AddTaskError(requestID scheduler.RequestID, err error) {
	state.ensureMaps()
	state.proto.TaskErrors[string(requestID)] = err.Error()
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
	c := make([]Cancellation, 0, len(state.proto.WorkerQueues)+len(state.proto.TaskErrors))
	for wid, q := range state.proto.WorkerQueues {
		if q.TaskToAbort != "" {
			c = append(c, Cancellation{RequestID: q.TaskToAbort, WorkerID: wid})
		}
	}
	for tid, err := range state.proto.TaskErrors {
		c = append(c, Cancellation{RequestID: tid, ErrorMessage: err})
	}
	return c
}

// NotifyTaskWaiting informs the quotascheduler about a waiting task.
func (state *State) NotifyTaskWaiting(ctx context.Context, s *scheduler.Scheduler, events scheduler.EventSink, update *TaskWaitingRequest) {
	state.ensureMaps()
	req := scheduler.NewTaskRequest(
		update.RequestID,
		update.AccountID,
		update.ProvisionableLabels,
		update.BaseLabels,
		update.EnqueueTime)
	s.AddRequest(ctx, req, update.Time, update.Tags, events)
}

// NotifyTaskRunning informs the quotascheduler about a running task.
func (state *State) NotifyTaskRunning(ctx context.Context, s *scheduler.Scheduler, events scheduler.EventSink, update *TaskRunningRequest) {
	state.ensureMaps()
	wid := update.WorkerID
	rid := update.RequestID
	// This NotifyRequest call ensures scheduler state consistency with
	// the latest update.
	s.NotifyTaskRunning(ctx, rid, wid, update.Time, events)
	if q, ok := state.proto.WorkerQueues[string(wid)]; ok {
		if !update.Time.Before(tutils.Timestamp(q.EnqueueTime)) {
			delete(state.proto.WorkerQueues, string(wid))
			logging.Debugf(ctx, "Reconciler: unexpected request %s on worker %s, clobbering WorkerQueue.", rid, wid)
		} else {
			logging.Debugf(ctx, "Reconciler: ignoring non-forward RUNNING notification with request %s on worker %s.", rid, wid)
			// TODO(akeshet): Consider whether we should delete from workerqueue
			// here for non-forward updates that are still a (wid, rid) match
			// for the expected assignment.
		}
	}
}

// NotifyTaskAbsent informs the quotascheduler about an absent task.
func (state *State) NotifyTaskAbsent(ctx context.Context, s *scheduler.Scheduler, events scheduler.EventSink, update *TaskAbsentRequest) {
	state.ensureMaps()
	rid := update.RequestID
	t := update.Time
	s.NotifyTaskAbsent(ctx, rid, t, events)
	// TODO(akeshet): Add an inverse map from aborting request -> previous
	// worker to avoid the need for this iteration through all workers.
	for wid, q := range state.proto.WorkerQueues {
		if q.TaskToAbort == string(rid) && tutils.Timestamp(q.EnqueueTime).Before(t) {
			delete(state.proto.WorkerQueues, wid)
		}
	}
	delete(state.proto.TaskErrors, string(rid))
}

// timeoutWorkers enforces the timeout for workers to pick up their assigned tasks.
func (state *State) timeoutWorkers(ctx context.Context, s *scheduler.Scheduler, t time.Time, events scheduler.EventSink) {
	for wid, q := range state.proto.WorkerQueues {
		qTime := tutils.Timestamp(q.EnqueueTime)
		if t.Sub(qTime) < WorkerQueueTimeout {
			continue
		}

		// Timed out waiting for worker to pick up its assigned task.
		if err := s.Unassign(ctx, scheduler.RequestID(q.TaskToAssign), scheduler.WorkerID(wid), t, events); err != nil {
			logging.Debugf(ctx, "%s", err.Error())
		}
		delete(state.proto.WorkerQueues, wid)
	}
}

// ensureMaps initializes any nil maps in reconciler.
//
// This is necessary because protobuf deserialization of an empty map returns a nil map.
func (state *State) ensureMaps() {
	if state.proto.WorkerQueues == nil {
		state.proto.WorkerQueues = make(map[string]*protos.WorkerQueue)
	}
	if state.proto.TaskErrors == nil {
		state.proto.TaskErrors = make(map[string]string)
	}
}
