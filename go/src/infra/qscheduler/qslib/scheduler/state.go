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

	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// applyAssignment applies the given Assignment to state.
func (s *State) applyAssignment(m *Assignment) {
	s.validateAssignment(m)

	cost := vector.New()

	// Determine initial cost, and apply and preconditions to starting the
	// new task run.
	switch m.Type {
	case Assignment_IDLE_WORKER:
		cost = vector.New()

	case Assignment_PREEMPT_WORKER:
		worker := s.Workers[m.WorkerId]
		cost = worker.RunningTask.Cost
		// Refund the cost of the preempted task.
		s.refundAccount(worker.RunningTask.Request.AccountId, cost)

		// Charge the preempting account for the cost of the preempted task.
		s.chargeAccount(s.QueuedRequests[m.RequestId].AccountId, cost)

		// Remove the preempted job and return it to the queue.
		s.reenqueueRunningRequest(m.TaskToAbort)
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
func (s *State) refundAccount(accountID string, cost *vector.Vector) {
	if _, ok := s.Balances[accountID]; ok {
		bal := s.Balances[accountID].Plus(*cost)
		s.Balances[accountID] = &bal
	}
}

// chargeAccount applies a cost-sized charge to the account with given id (if it
// exists).
func (s *State) chargeAccount(accountID string, cost *vector.Vector) {
	if _, ok := s.Balances[accountID]; ok {
		bal := s.Balances[accountID].Minus(*cost)
		s.Balances[accountID] = &bal
	}
}

// startRunning starts the given requestID on the given workerID.
// It does not validate inputs, so it should only be called if that worker
// and request currently exist and are idle.
func (s *State) startRunning(requestID string, workerID string,
	priority int32, initialCost *vector.Vector) {
	s.ensureCache()
	rt := &task.Run{
		Priority:  priority,
		Request:   s.QueuedRequests[requestID],
		Cost:      initialCost.Copy(),
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

// reenqueueRunningRequest moves the given request back into the queue, if it exists
// and is running. Otherwise it does nothing.
func (s *State) reenqueueRunningRequest(requestID string) {
	s.ensureCache()
	if workerID, ok := s.RunningRequestsCache[requestID]; ok {
		w := s.Workers[workerID]
		request := w.RunningTask.Request
		w.RunningTask = nil
		delete(s.RunningRequestsCache, requestID)
		s.QueuedRequests[requestID] = request
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
