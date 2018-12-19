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
	"time"

	"infra/qscheduler/qslib/tutils"
)

// state represents the state of quota scheduler.
type state struct {
	// queuedRequests is the set of Requests that are waiting to be assigned to a
	// worker, keyed by request id.
	queuedRequests map[RequestID]*request

	// balance of all quota accounts for this pool, keyed by account id.
	// TODO(akeshet): Turn this into map[string]*balance, and then get rid of a bunch of
	// unnecessary array copying.
	balances map[AccountID]balance

	// workers that may run tasks, and their states, keyed by worker id.
	workers map[WorkerID]*worker

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

// request represents a queued or running task request.
type request struct {
	// accountID is the id of the account that this request charges to.
	accountID AccountID

	// enqueueTime is the time at which the request was enqueued.
	enqueueTime time.Time

	// labels is the set of Provisionable Labels for this task.
	labels []string

	// confirmedTime is the most recent time at which the Request state was
	// provided or confirmed by external authority (via a call to Enforce or
	// AddRequest).
	confirmedTime time.Time
}

func newTaskRequest(r *request) *TaskRequest {
	return &TaskRequest{
		AccountId:     string(r.accountID),
		ConfirmedTime: tutils.TimestampProto(r.confirmedTime),
		EnqueueTime:   tutils.TimestampProto(r.enqueueTime),
		Labels:        r.labels,
	}
}

// taskRun represents the run-related information about a running task.
type taskRun struct {
	// cost is the total cost that has been incurred on this task while running.
	// TODO(akeshet): Turn this into map[string]*balance, and then get rid of a bunch of
	// unnecessary array copying.
	cost balance

	// request is the request that this running task corresponds to.
	request *request

	// requestID is the request id of the request that this running task
	// corresponds to.
	requestID RequestID

	// priority is the current priority level of the running task.
	priority int
}

// worker represents a running or idle worker capable of running tasks.
type worker struct {
	// labels represents the set of provisionable labels that this worker
	// possesses.
	labels []string

	// runningTask is, if non-nil, the task that is currently running on the
	// worker.
	runningTask *taskRun

	// confirmedTime is the most recent time at which the Worker state was
	// directly confirmed as idle by external authority (via a call to MarkIdle or
	// NotifyRequest).
	confirmedTime time.Time
}

// AddRequest enqueues a new task request with the given time, (or if the task
// exists already, notifies that the task was idle at the given time).
func (s *state) addRequest(ctx context.Context, requestID RequestID, r *TaskRequest, t time.Time) {
	if _, ok := s.getRequest(requestID); ok {
		// Request already exists, simply notify that it should be idle at the
		// given time.
		s.notifyRequest(ctx, requestID, "", t)
	} else {
		rr := &request{
			accountID:     AccountID(r.AccountId),
			confirmedTime: tutils.Timestamp(r.ConfirmedTime),
			enqueueTime:   tutils.Timestamp(r.EnqueueTime),
			labels:        r.Labels,
		}
		rr.confirm(t)
		s.queuedRequests[requestID] = rr
	}
}

// markIdle implements MarkIdle for a given state.
func (s *state) markIdle(workerID WorkerID, labels LabelSet, t time.Time) {
	w, ok := s.workers[workerID]
	if !ok {
		// This is a new worker, create it and return.
		s.workers[workerID] = &worker{confirmedTime: t, labels: labels}
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

	w.labels = labels
	w.confirm(t)

	if w.isIdle() {
		// Our worker was already idle and we've updated its labels and idle time, so
		// we're done.
		return
	}

	// Our worker wasn't previously idle. Remove the previous request it was
	// running.
	previousRequestID := w.runningTask.requestID
	s.deleteRequest(previousRequestID)
}

// notifyRequest implements Scheduler.NotifyRequest for a given State.
func (s *state) notifyRequest(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time) {
	if requestID == "" {
		panic("Must supply a requestID.")
	}

	if request, ok := s.getRequest(requestID); ok {
		if !t.Before(request.confirmedTime) {
			s.updateRequest(ctx, requestID, workerID, t, request)
		}
	} else {
		// The request didn't exist, but the notification might be more up to date
		// that our information about the worker, in which case delete the worker.
		s.deleteWorkerIfOlder(workerID, t)
	}
}

// abortRequest implements Scheduler.AbortRequest for a given State.
func (s *state) abortRequest(ctx context.Context, requestID RequestID, t time.Time) {
	// Reuse the notifyRequest logic. First, notify that task is not running. Then, remove
	// the request from queue if it is present.
	s.notifyRequest(ctx, requestID, "", t)
	if req, ok := s.getRequest(requestID); ok {
		if !t.Before(req.confirmedTime) {
			s.deleteRequest(requestID)
		}
	}
}

// getRequest looks up the given requestID among either the running or queued
// tasks, and returns (the request if it exists, boolean indication if
// request exists).
func (s *state) getRequest(requestID RequestID) (r *request, ok bool) {
	s.ensureCache()
	if wid, ok := s.runningRequestsCache[requestID]; ok {
		return s.workers[wid].runningTask.request, true
	}
	r, ok = s.queuedRequests[requestID]
	return r, ok
}

// updateRequest fixes stale opinion about the given request. This method should
// only be called for requests that were already determined to be stale relative
// to time t.
func (s *state) updateRequest(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time,
	r *request) {
	s.ensureCache()
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

	if workerID == "" {
		// We thought the request was running on a worker, but were notified it
		// is idle.
		allegedWorker := s.workers[allegedWorkerID]

		if t.Before(allegedWorker.latestConfirmedTime()) {
			// However, the worker was marked idle more recently than this notification's
			// timestamp, and was later matched to this request by the scheduler.
			// This probably means that this notification is a late delivery of a
			// message that was emitted after the scheduler assignment.
			// Ignore it.
			//
			// NOTE: Revisit if this is the actual desired behavior. If the assignment
			// of the request to the worker was dropped or ignored by swarming, then
			// the inconsistency will only be healed by a future call to either MarkIdle
			// for this worker or Notify for this request.
			//
			// TODO(akeshet): Once a logging or metrics layer is added, log the fact
			// that this has occurred.
			return
		}
		// The request should be queued, although it is not. Fix this by putting the
		// request into the queue and removing the alleged worker.
		s.deleteWorker(allegedWorkerID)
		r.confirmedTime = t
		s.queuedRequests[requestID] = r
		return
	}

	if allegedWorkerID != "" {
		// The request was believed to be non-idle, but is running on a different
		// worker than expected. Delete this worker and request.
		s.deleteWorker(allegedWorkerID)
	}

	// If our information about workerID is older than this notification, then
	// delete it and its request too.
	s.deleteWorkerIfOlder(workerID, t)
}

// deleteWorkerIfOlder deletes the worker with the given ID (along with any
// request it was running) if its confirmed time and that of any
// request it is running is older than t.
func (s *state) deleteWorkerIfOlder(workerID WorkerID, t time.Time) {
	if worker, ok := s.workers[workerID]; ok {
		if !t.Before(worker.latestConfirmedTime()) {
			s.deleteWorker(workerID)
		}
	}
}

// applyAssignment applies the given Assignment to state.
func (s *state) applyAssignment(m *Assignment) {
	s.validateAssignment(m)

	cost := balance{}

	// If preempting, determine initial cost, and apply and preconditions
	// to starting the new task run.
	if m.Type == AssignmentPreemptWorker {
		worker := s.workers[m.WorkerID]
		cost = worker.runningTask.cost
		// Refund the cost of the preempted task.
		s.refundAccount(worker.runningTask.request.accountID, cost)

		// Charge the preempting account for the cost of the preempted task.
		s.chargeAccount(s.queuedRequests[m.RequestID].accountID, cost)

		// Remove the preempted job from worker.
		oldRequestID := worker.runningTask.requestID
		s.deleteRequest(oldRequestID)
	}

	// Start the new task run.
	s.startRunning(m.RequestID, m.WorkerID, int(m.Priority), cost)
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
		if !worker.isIdle() {
			panic(fmt.Sprintf("Worker %s is not idle, it is running task %s.",
				m.WorkerID, worker.runningTask.requestID))
		}

	case AssignmentPreemptWorker:
		if worker.isIdle() {
			panic(fmt.Sprintf("Worker %s is idle, expected running task %s.",
				m.WorkerID, m.TaskToAbort))
		}
		runningID := worker.runningTask.requestID
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
// TODO(akeshet): Update this and the related methods to accept a *balance argument
// rather than balance, to avoid a lot of unneeded array copying.
func (s *state) refundAccount(accountID AccountID, cost balance) {
	if _, ok := s.balances[accountID]; ok {
		bal := s.balances[accountID].Plus(cost)
		s.balances[accountID] = bal
	}
}

// chargeAccount applies a cost-sized charge to the account with given id (if it
// exists).
func (s *state) chargeAccount(accountID AccountID, cost balance) {
	if _, ok := s.balances[accountID]; ok {
		bal := s.balances[accountID].Minus(cost)
		s.balances[accountID] = bal
	}
}

// startRunning starts the given requestID on the given workerID.
// It does not validate inputs, so it should only be called if that worker
// and request currently exist and are idle.
func (s *state) startRunning(requestID RequestID, workerID WorkerID, priority int, initialCost balance) {
	s.ensureCache()

	rt := &taskRun{
		priority:  priority,
		request:   s.queuedRequests[requestID],
		cost:      initialCost,
		requestID: requestID,
	}
	s.workers[workerID].runningTask = rt
	delete(s.queuedRequests, requestID)
	s.runningRequestsCache[requestID] = workerID
}

// deleteWorker deletes the worker with the given ID (along with any task
// it is running).
func (s *state) deleteWorker(workerID WorkerID) {
	if worker, ok := s.workers[workerID]; ok {
		if !worker.isIdle() {
			s.ensureCache()
			delete(s.runningRequestsCache, worker.runningTask.requestID)
		}
		delete(s.workers, workerID)
	}
}

// deleteRequest deletes the request with the given ID, whether it is running
// or queued. If the request is neither running nor enqueued, it does nothing.
func (s *state) deleteRequest(requestID RequestID) {
	// TODO(akeshet): eliminate most of these calls to ensureCache() by
	// by adding a getWorkerForRequest method.
	s.ensureCache()
	if _, ok := s.queuedRequests[requestID]; ok {
		delete(s.queuedRequests, requestID)
	} else if workerID, ok := s.runningRequestsCache[requestID]; ok {
		worker := s.workers[workerID]
		worker.runningTask = nil
		delete(s.runningRequestsCache, requestID)
	}
}

// ensureCache ensures that the running request cache exists and regenerates it
// if necessary. It should be called before attempting to access
// RunningRequestCache.
func (s *state) ensureCache() {
	if s.runningRequestsCache == nil {
		s.regenCache()
	}
}

// regenCache recomputes and stores the RunningRequestsCache.
func (s *state) regenCache() {
	s.runningRequestsCache = make(map[RequestID]WorkerID)
	for wid, w := range s.workers {
		if w.isIdle() {
			continue
		}
		rid := w.runningTask.requestID
		if existing, ok := s.runningRequestsCache[rid]; ok {
			panic(fmt.Sprintf(
				"Duplicate workers %s and %s assigned to a single request %s",
				wid, existing, rid))
		}
		s.runningRequestsCache[rid] = wid
	}
}
