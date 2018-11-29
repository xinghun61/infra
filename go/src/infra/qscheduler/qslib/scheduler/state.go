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
	"fmt"
	"time"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/vector"
)

// AddRequest enqueues a new task request with the given time, (or if the task
// exists already, notifies that the task was idle at the given time).
func (s *State) addRequest(requestID string, request *TaskRequest, t time.Time) {
	if _, ok := s.getRequest(requestID); ok {
		// Request already exists, simply notify that it should be idle at the
		// given time.
		s.notifyRequest(requestID, "", t)
	} else {
		request.confirm(t)
		s.QueuedRequests[requestID] = request
	}
}

// markIdle implements MarkIdle for a given state.
func (s *State) markIdle(workerID string, labels LabelSet, t time.Time) {
	worker, ok := s.Workers[workerID]
	if !ok {
		// This is a new worker, create it and return.
		s.Workers[workerID] = &Worker{ConfirmedTime: tutils.TimestampProto(t), Labels: labels}
		return
	}

	// Ignore call if our state is newer.
	if t.Before(worker.latestConfirmedTime()) {
		if !t.Before(tutils.Timestamp(worker.ConfirmedTime)) {
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

	worker.Labels = labels
	worker.confirm(t)

	if worker.isIdle() {
		// Our worker was already idle and we've updated its labels and idle time, so
		// we're done.
		return
	}

	// Our worker wasn't previously idle. Remove the previous request it was
	// running.
	previousRequestID := worker.RunningTask.RequestId
	s.deleteRequest(previousRequestID)
}

// notifyRequest implements Scheduler.NotifyRequest for a given State.
func (s *State) notifyRequest(requestID string, workerID string, t time.Time) {
	if requestID == "" {
		panic("Must supply a requestID.")
	}

	if request, ok := s.getRequest(requestID); ok {
		if !t.Before(tutils.Timestamp(request.ConfirmedTime)) {
			s.updateRequest(requestID, workerID, t, request)
		}
	} else {
		// The request didn't exist, but the notification might be more up to date
		// that our information about the worker, in which case delete the worker.
		s.deleteWorkerIfOlder(workerID, t)
	}
}

// abortRequest implements Scheduler.AbortRequest for a given State.
func (s *State) abortRequest(requestID string, t time.Time) {
	// Reuse the notifyRequest logic. First, notify that task is not running. Then, remove
	// the request from queue if it is present.
	s.notifyRequest(requestID, "", t)
	if req, ok := s.getRequest(requestID); ok {
		if !t.Before(tutils.Timestamp(req.ConfirmedTime)) {
			s.deleteRequest(requestID)
		}
	}
}

// getRequest looks up the given requestID among either the running or queued
// tasks, and returns (the request if it exists, boolean indication if
// request exists).
func (s *State) getRequest(requestID string) (r *TaskRequest, ok bool) {
	s.ensureCache()
	if wid, ok := s.RunningRequestsCache[requestID]; ok {
		return s.Workers[wid].RunningTask.Request, true
	}
	r, ok = s.QueuedRequests[requestID]
	return r, ok
}

// updateRequest fixes stale opinion about the given request. This method should
// only be called for requests that were already determined to be stale relative
// to time t.
func (s *State) updateRequest(requestID string, workerID string, t time.Time,
	r *TaskRequest) {
	s.ensureCache()
	allegedWorkerID, isRunning := s.RunningRequestsCache[requestID]
	if allegedWorkerID == workerID {
		// Our state is already correct, so just update times and we are done.
		r.confirm(t)
		if isRunning {
			// Also update the worker's time, if this is a forward-in-time update
			// for it.
			worker := s.Workers[allegedWorkerID]
			worker.confirm(t)
		}
		return
	}

	if workerID == "" {
		// We thought the request was running on a worker, but were notified it
		// is idle.
		allegedWorker := s.Workers[allegedWorkerID]

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
		r.ConfirmedTime = tutils.TimestampProto(t)
		s.QueuedRequests[requestID] = r
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
func (s *State) deleteWorkerIfOlder(workerID string, t time.Time) {
	if worker, ok := s.Workers[workerID]; ok {
		if !t.Before(worker.latestConfirmedTime()) {
			s.deleteWorker(workerID)
		}
	}
}

// applyAssignment applies the given Assignment to state.
func (s *State) applyAssignment(m *Assignment) {
	s.validateAssignment(m)

	// Nil here will be treated as 0 cost by startRunning call below.
	var cost *vector.Vector

	// If preempting, determine initial cost, and apply and preconditions
	// to starting the new task run.
	if m.Type == Assignment_PREEMPT_WORKER {
		worker := s.Workers[m.WorkerId]
		cost = worker.RunningTask.Cost
		// Refund the cost of the preempted task.
		s.refundAccount(worker.RunningTask.Request.AccountId, *cost)

		// Charge the preempting account for the cost of the preempted task.
		s.chargeAccount(s.QueuedRequests[m.RequestId].AccountId, *cost)

		// Remove the preempted job from worker.
		oldRequestID := worker.RunningTask.RequestId
		s.deleteRequest(oldRequestID)
	}

	// Start the new task run.
	s.startRunning(m.RequestId, m.WorkerId, m.Priority, cost)
}

// validateAssignment ensures that all the expected preconditions of the given
// Assignment are true, and panics otherwise.
func (s *State) validateAssignment(m *Assignment) {
	// Assignment-type-agnostic checks.
	if _, ok := s.QueuedRequests[m.RequestId]; !ok {
		panic(fmt.Sprintf("No request with id %s.", m.RequestId))
	}

	worker, ok := s.Workers[m.WorkerId]
	if !ok {
		panic(fmt.Sprintf("No worker with id %s", m.WorkerId))
	}

	// Assignment-type-specific checks.
	switch m.Type {
	case Assignment_IDLE_WORKER:
		if !worker.isIdle() {
			panic(fmt.Sprintf("Worker %s is not idle, it is running task %s.",
				m.WorkerId, worker.RunningTask.RequestId))
		}

	case Assignment_PREEMPT_WORKER:
		if worker.isIdle() {
			panic(fmt.Sprintf("Worker %s is idle, expected running task %s.",
				m.WorkerId, m.TaskToAbort))
		}
		runningID := worker.RunningTask.RequestId
		if runningID != m.TaskToAbort {
			panic(fmt.Sprintf("Worker %s is running task %s, expected %s.", m.WorkerId,
				runningID, m.TaskToAbort))
		}

	default:
		panic(fmt.Sprintf("Unknown assignment type %s.", m.Type))
	}
}

// refundAccount applies a cost-sized refund to account with given id (if it
// exists).
func (s *State) refundAccount(accountID string, cost vector.Vector) {
	if _, ok := s.Balances[accountID]; ok {
		bal := s.Balances[accountID].Plus(cost)
		s.Balances[accountID] = &bal
	}
}

// chargeAccount applies a cost-sized charge to the account with given id (if it
// exists).
func (s *State) chargeAccount(accountID string, cost vector.Vector) {
	if _, ok := s.Balances[accountID]; ok {
		bal := s.Balances[accountID].Minus(cost)
		s.Balances[accountID] = &bal
	}
}

// startRunning starts the given requestID on the given workerID.
// It does not validate inputs, so it should only be called if that worker
// and request currently exist and are idle.
func (s *State) startRunning(requestID string, workerID string,
	priority int32, initialCost *vector.Vector) {
	if initialCost == nil {
		initialCost = vector.New()
	} else {
		initialCost = initialCost.Copy()
	}
	s.ensureCache()
	rt := &TaskRun{
		Priority:  priority,
		Request:   s.QueuedRequests[requestID],
		Cost:      initialCost,
		RequestId: requestID,
	}
	s.Workers[workerID].RunningTask = rt
	delete(s.QueuedRequests, requestID)
	s.RunningRequestsCache[requestID] = workerID
}

// deleteWorker deletes the worker with the given ID (along with any task
// it is running).
func (s *State) deleteWorker(workerID string) {
	if worker, ok := s.Workers[workerID]; ok {
		if !worker.isIdle() {
			s.ensureCache()
			delete(s.RunningRequestsCache, worker.RunningTask.RequestId)
		}
		delete(s.Workers, workerID)
	}
}

// deleteRequest deletes the request with the given ID, whether it is running
// or queued. If the request is neither running nor enqueued, it does nothing.
func (s *State) deleteRequest(requestID string) {
	// TODO(akeshet): eliminate most of these calls to ensureCache() by
	// by adding a getWorkerForRequest method.
	s.ensureCache()
	if _, ok := s.QueuedRequests[requestID]; ok {
		delete(s.QueuedRequests, requestID)
	} else if workerID, ok := s.RunningRequestsCache[requestID]; ok {
		worker := s.Workers[workerID]
		worker.RunningTask = nil
		delete(s.RunningRequestsCache, requestID)
	}
}

// ensureCache ensures that the running request cache exists and regenerates it
// if necessary. It should be called before attempting to access
// RunningRequestCache.
func (s *State) ensureCache() {
	if s.RunningRequestsCache == nil {
		s.regenCache()
	}
}

// regenCache recomputes and stores the RunningRequestsCache.
func (s *State) regenCache() {
	s.RunningRequestsCache = make(map[string]string)
	for wid, w := range s.Workers {
		if w.isIdle() {
			continue
		}
		rid := w.RunningTask.RequestId
		if existing, ok := s.RunningRequestsCache[rid]; ok {
			panic(fmt.Sprintf(
				"Duplicate workers %s and %s assigned to a single request %s",
				wid, existing, rid))
		}
		s.RunningRequestsCache[rid] = wid
	}
}
