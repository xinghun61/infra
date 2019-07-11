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

package scheduler

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/protos/metrics"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

// state represents the state of quota scheduler.
type state struct {
	// queuedRequests is the set of Requests that are waiting to be assigned to a
	// worker, keyed by request id.
	queuedRequests map[RequestID]*TaskRequest

	// balance of all quota accounts for this pool, keyed by account id.
	balances map[AccountID]Balance

	// workers that may run tasks, and their states, keyed by worker id.
	workers map[WorkerID]*Worker

	lastUpdateTime time.Time

	// runningRequestsCache is logically the inverse of Workers, a map from request id
	// to worker id for running tasks. This is used to optimize certain lookups, however
	// workers is the authoritative source.
	runningRequestsCache map[RequestID]WorkerID

	// TODO(akeshet): Add a store of (completed request id, timestamp) that will
	// allow us to remember all the tasks that were completed within the last
	// X hours, and ignore any possible extremely-stale AddRequest calls we get
	// about them.
}

// fanoutGroup identifies the group (for a given request) over which per-account
// per-image fanout limits will be enforced.
type fanoutGroup string

// TaskRequest represents a queued or running task TaskRequest.
type TaskRequest struct {
	// ID is the ID of this request.
	ID RequestID

	// AccountID is the id of the account that this request charges to.
	AccountID AccountID

	// EnqueueTime is the time at which the request was enqueued.
	EnqueueTime time.Time

	// ProvisionableLabels is the set of Provisionable Labels for this task.
	ProvisionableLabels stringset.Set

	// BaseLabels is the set of base labels for this task.
	BaseLabels stringset.Set

	// confirmedTime is the most recent time at which the Request state was
	// provided or confirmed by external authority (via a call to Enforce or
	// AddRequest).
	confirmedTime time.Time

	// examinedTime is the most recent time at which the Request participated
	// in a scheduler pass, without being ignored (due to fanout limit) and
	// without being matched to a worker.
	examinedTime time.Time
}

// ConfirmedTime returns the latest time at which the task request's state was
// confirmed by source of truth (swarming).
func (t *TaskRequest) ConfirmedTime() time.Time {
	return t.confirmedTime
}

// requestProto converts a request to a TaskRequest proto. It is a convenience method.
// Note: TaskRequest does not include the request's ID, so this conversion is lossy.
func requestProto(r *TaskRequest, mb *mapBuilder) *protos.TaskRequest {
	return &protos.TaskRequest{
		AccountId:             string(r.AccountID),
		ConfirmedTime:         tutils.TimestampProto(r.confirmedTime),
		ExaminedTime:          tutils.TimestampProto(r.examinedTime),
		EnqueueTime:           tutils.TimestampProto(r.EnqueueTime),
		ProvisionableLabelIds: mb.ForSet(r.ProvisionableLabels),
		BaseLabelIds:          mb.ForSet(r.BaseLabels),
	}
}

// fanoutGroup returns a string that uniquely identifies this task's account
// and provisionable labels, and thus identifies the fanout group to be
// used for this account.
//
// TODO(akeshet): Memoize the return value to avoid cost of recomputation.
func (t *TaskRequest) fanoutGroup() fanoutGroup {
	if t.AccountID == "" {
		return ""
	}

	provisionable := t.ProvisionableLabels.ToSlice()
	sort.Strings(provisionable)

	elems := []string{string(t.AccountID)}
	elems = append(elems, provisionable...)
	// This separator is just an arbitrary string that is very unlikely to be
	// encountered in the wild in account IDs or provisionable labels.
	const separator = "$;~$"
	return fanoutGroup(strings.Join(elems, separator))
}

// taskRun represents the run-related information about a running task.
type taskRun struct {
	// cost is the total cost that has been incurred on this task while running.
	cost Balance

	// request is the request that this running task corresponds to.
	request *TaskRequest

	// priority is the current priority level of the running task.
	priority Priority
}

// Worker represents a running or idle Worker capable of running tasks.
type Worker struct {
	// ID is the ID of this worker.
	ID WorkerID

	// Labels represents the set of Labels that this worker possesses.
	Labels stringset.Set

	// runningTask is, if non-nil, the task that is currently running on the
	// worker.
	runningTask *taskRun

	// confirmedTime is the most recent time at which the Worker state was
	// directly confirmed as idle by external authority (via a call to MarkIdle or
	// NotifyRequest).
	confirmedTime time.Time

	// modifiedTime is the most recent time at which the Worker either became
	// idle or had its labels change.
	modifiedTime time.Time
}

// ConfirmedTime returns the latest time at which the worker's state was
// confirmed by source of truth (swarming).
func (w *Worker) ConfirmedTime() time.Time {
	return w.latestConfirmedTime()
}

// addRequest enqueues a new task request with the given time, (or if the task
// exists already, notifies that the task was idle at the given time).
func (s *state) addRequest(ctx context.Context, r *TaskRequest, t time.Time, tags []string, e EventSink) {
	if r.ID == "" {
		panic("empty request id")
	}
	rid := r.ID

	knownRequest, alreadyKnown := s.getRequest(rid)
	if !alreadyKnown {
		// Request is not already known. Add it.
		s.addNewRequest(ctx, r, t, tags, e)
		return
	}

	// Request is already known.
	wid, running := s.runningRequestsCache[rid]
	if !running {
		// Request was already idle. Just update request's confirmed time.
		knownRequest.confirm(t)
		return
	}

	// Request was running.
	w := s.workers[wid]
	if !t.Before(knownRequest.confirmedTime) && !t.Before(w.confirmedTime) {
		// This notification is newer than the known state of request.
		// Respect it.
		s.deleteWorker(wid)
		s.addNewRequest(ctx, r, t, tags, e)
	}
}

// addNewRequest immediately adds the given request to the queue.
func (s *state) addNewRequest(ctx context.Context, r *TaskRequest, t time.Time, tags []string, e EventSink) {
	r.confirm(t)
	s.queuedRequests[r.ID] = r
	e.AddEvent(eventEnqueued(r, s, t,
		&metrics.TaskEvent_EnqueuedDetails{Tags: tags}))
}

// TODO(akeshet): Move this helper method to the stringset library.
func setEquals(a stringset.Set, b stringset.Set) bool {
	if a.Len() != b.Len() {
		return false
	}
	return a.Contains(b)
}

// markIdle implements MarkIdle for a given state.
func (s *state) markIdle(workerID WorkerID, labels stringset.Set, t time.Time, e EventSink) {
	w, ok := s.workers[workerID]
	if !ok {
		// This is a new worker, create it and return.
		s.workers[workerID] = &Worker{ID: workerID, confirmedTime: t, modifiedTime: s.lastUpdateTime, Labels: labels}
		return
	}

	// Ignore call if our state is newer.
	if t.Before(w.latestConfirmedTime()) {
		if !t.Before(w.confirmedTime) {
			// TODO(akeshet): Once a diagnostic/logging layer exists, log this case.
			// This case means that the following order of events happened:
			// 1) We marked worker as idle at t=0.
			// 2) We received a request at t=2, and matched it to that worker.
			// 3) We received an "is idle" call for that worker at t=1.
			//
			// This is most likely due to out-of-order message delivery. In any case
			// it should be fairly harmless, as it will self-heal once we receive a
			// later markIdle call for this worker or notifyRequest for this
			// match at t=3.
		}
		return
	}

	if !setEquals(w.Labels, labels) {
		w.Labels = labels
		w.modifiedTime = s.lastUpdateTime
	}

	w.confirm(t)

	if w.IsIdle() {
		// Our worker was already idle and we've updated its labels and idle time, so
		// we're done.
		return
	}

	// Our worker wasn't previously idle. Remove the previous request it was
	// running.
	w.modifiedTime = s.lastUpdateTime
	previousRequest := w.runningTask.request
	e.AddEvent(eventCompleted(previousRequest, w, s, t,
		&metrics.TaskEvent_CompletedDetails{Reason: metrics.TaskEvent_CompletedDetails_BOT_IDLE}))
	s.deleteRequest(previousRequest.ID)
}

// notifyTaskRunning implements Scheduler.NotifyTaskRunning for a given State.
func (s *state) notifyTaskRunning(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time, e EventSink) {
	if workerID == "" {
		panic("empty workerID")
	}
	if requestID == "" {
		panic("empty requestID")
	}

	if request, ok := s.getRequest(requestID); ok {
		if !t.Before(request.confirmedTime) {
			s.updateRequest(ctx, requestID, workerID, t, request, e)
		}
	} else {
		// The request didn't exist, but the notification might be more up to date
		// that our information about the worker, in which case delete the worker.
		s.deleteInconsistentWorkerIfOlder(workerID, t, requestID, e)
	}
}

// notifyTaskAbsent implements Scheduler.NotifyTaskAbsent for a given State.
func (s *state) notifyTaskAbsent(ctx context.Context, requestID RequestID, t time.Time, e EventSink) {
	r, ok := s.getRequest(requestID)
	if !ok {
		// Task was already absent.
		return
	}

	if wid, ok := s.runningRequestsCache[requestID]; ok {
		// Task was running.
		w := s.workers[wid]
		if !t.Before(w.confirmedTime) && !t.Before(r.confirmedTime) {

			e.AddEvent(eventCompleted(r, w, s, t,
				&metrics.TaskEvent_CompletedDetails{Reason: metrics.TaskEvent_CompletedDetails_RUNNING_TASK_ABSENT}))
			s.deleteWorker(wid)
		}
		return
	}

	// Task was waiting.
	if !t.Before(r.confirmedTime) {
		e.AddEvent(eventCompleted(r, nil, s, t,
			&metrics.TaskEvent_CompletedDetails{Reason: metrics.TaskEvent_CompletedDetails_IDLE_TASK_ABSENT}))
		s.deleteRequest(requestID)
	}
}

// getRequest looks up the given requestID among either the running or queued
// tasks, and returns (the request if it exists, boolean indication if
// request exists).
func (s *state) getRequest(requestID RequestID) (*TaskRequest, bool) {
	if wid, ok := s.runningRequestsCache[requestID]; ok {
		return s.workers[wid].runningTask.request, true
	}
	r, ok := s.queuedRequests[requestID]
	return r, ok
}

// updateRequest fixes stale opinion about the given request. This method should
// only be called for requests that were already determined to be stale relative
// to time t.
func (s *state) updateRequest(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time,
	r *TaskRequest, e EventSink) {
	if requestID == "" {
		panic("empty request ID")
	}
	if workerID == "" {
		panic("empty worker ID")
	}
	allegedWorkerID, isRunning := s.runningRequestsCache[requestID]
	if allegedWorkerID == workerID {
		// Our state is already correct, so just update times and we are done.
		r.confirm(t)
		if isRunning {
			// Also update the worker's time, if this is a forward-in-time update
			// for it.
			worker := s.workers[allegedWorkerID]
			worker.confirm(t)
		}
		return
	}

	if isRunning {
		// The request was believed to be non-idle, but is running on a different
		// worker than expected. Delete this worker and request.
		allegedWorker := s.workers[allegedWorkerID]
		e.AddEvent(eventCompleted(r, allegedWorker, s, t,
			&metrics.TaskEvent_CompletedDetails{
				Reason:   metrics.TaskEvent_CompletedDetails_INCONSISTENT_BOT_FOR_TASK,
				OtherBot: string(workerID),
			}))
		s.deleteWorker(allegedWorkerID)
	}

	// If our information about workerID is older than this notification, then
	// delete it and its request too.
	s.deleteInconsistentWorkerIfOlder(workerID, t, requestID, e)
}

// deleteInconsistentWorkerIfOlder deletes the worker with the given ID (along with any
// request it was running) if its confirmed time and that of any
// request it is running is older than t.
func (s *state) deleteInconsistentWorkerIfOlder(workerID WorkerID, t time.Time, cause RequestID, e EventSink) {
	if worker, ok := s.workers[workerID]; ok {
		if !t.Before(worker.latestConfirmedTime()) {
			if !worker.IsIdle() {
				e.AddEvent(eventCompleted(worker.runningTask.request, worker, s, t,
					&metrics.TaskEvent_CompletedDetails{
						Reason:    metrics.TaskEvent_CompletedDetails_INCONSISTENT_TASK_FOR_BOT,
						OtherTask: string(cause),
					}))
			}
			s.deleteWorker(workerID)
		}
	}
}

// applyAssignment applies the given Assignment to state.
func (s *state) applyAssignment(m *Assignment) {
	s.validateAssignment(m)

	var cost Balance

	// If preempting, determine initial cost, and apply and preconditions
	// to starting the new task run.
	if m.Type == AssignmentPreemptWorker {
		worker := s.workers[m.WorkerID]
		cost = worker.runningTask.cost
		// Refund the cost of the preempted task.
		s.refundAccount(worker.runningTask.request.AccountID, &cost)

		// Charge the preempting account for the cost of the preempted task.
		s.chargeAccount(s.queuedRequests[m.RequestID].AccountID, &cost)

		// Remove the preempted job from worker.
		oldRequestID := worker.runningTask.request.ID
		// Note: no COMPLETED metric is emitted here, because a PREEMPTED metric
		// has already been emitted by the scheduler.
		s.deleteRequest(oldRequestID)
	}

	// Start the new task run.
	s.startRunning(m.RequestID, m.WorkerID, m.Priority, cost)
}

// validateAssignment ensures that all the expected preconditions of the given
// Assignment are true, and panics otherwise.
func (s *state) validateAssignment(m *Assignment) {
	// Assignment-type-agnostic checks.
	if _, ok := s.queuedRequests[m.RequestID]; !ok {
		panic(fmt.Sprintf("No request with id %s.", m.RequestID))
	}

	worker, ok := s.workers[m.WorkerID]
	if !ok {
		panic(fmt.Sprintf("No worker with id %s", m.WorkerID))
	}

	// Assignment-type-specific checks.
	switch m.Type {
	case AssignmentIdleWorker:
		if !worker.IsIdle() {
			panic(fmt.Sprintf("Worker %s is not idle, it is running task %s.",
				m.WorkerID, worker.runningTask.request.ID))
		}

	case AssignmentPreemptWorker:
		if worker.IsIdle() {
			panic(fmt.Sprintf("Worker %s is idle, expected running task %s.",
				m.WorkerID, m.TaskToAbort))
		}
		runningID := worker.runningTask.request.ID
		if runningID != m.TaskToAbort {
			panic(fmt.Sprintf("Worker %s is running task %s, expected %s.", m.WorkerID,
				runningID, m.TaskToAbort))
		}

	default:
		panic(fmt.Sprintf("Unknown assignment type %d.", m.Type))
	}
}

// refundAccount applies a cost-sized refund to account with given id (if it
// exists).
func (s *state) refundAccount(accountID AccountID, cost *Balance) {
	if _, ok := s.balances[accountID]; ok {
		s.balances[accountID] = s.balances[accountID].Add(cost)
	}
}

// chargeAccount applies a cost-sized charge to the account with given id (if it
// exists).
func (s *state) chargeAccount(accountID AccountID, cost *Balance) {
	if _, ok := s.balances[accountID]; ok {
		s.balances[accountID] = s.balances[accountID].Sub(cost)
	}
}

// startRunning starts the given requestID on the given workerID.
// It does not validate inputs, so it should only be called if that worker
// and request currently exist and are idle.
func (s *state) startRunning(requestID RequestID, workerID WorkerID, priority Priority, initialCost Balance) {
	rt := &taskRun{
		priority: priority,
		request:  s.queuedRequests[requestID],
		cost:     initialCost,
	}
	s.workers[workerID].runningTask = rt
	delete(s.queuedRequests, requestID)
	s.runningRequestsCache[requestID] = workerID
}

// deleteWorker deletes the worker with the given ID (along with any task
// it is running).
func (s *state) deleteWorker(workerID WorkerID) {
	if worker, ok := s.workers[workerID]; ok {
		if !worker.IsIdle() {
			delete(s.runningRequestsCache, worker.runningTask.request.ID)
		}
		delete(s.workers, workerID)
	}
}

// deleteRequest deletes the request with the given ID, whether it is running
// or queued. If the request is neither running nor enqueued, it does nothing.
func (s *state) deleteRequest(requestID RequestID) {
	if _, ok := s.queuedRequests[requestID]; ok {
		delete(s.queuedRequests, requestID)
	} else if workerID, ok := s.runningRequestsCache[requestID]; ok {
		worker := s.workers[workerID]
		worker.runningTask = nil
		delete(s.runningRequestsCache, requestID)
	}
}
