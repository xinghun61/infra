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
Package scheduler provides Scheduler, which is an implementation of the
quotascheduler algorithm. The algorithm priorities and matches requests to workers,
tracks account balances, and ensures consistency between the scheduler's estimate
of Request and Worker states and the client-supplied authoritative state.

scheduler.Scheduler is an implementation of the reconciler.Scheduler interface.

See the provided example in this packages godoc or doc_test.go for usage.
*/
package scheduler

import (
	"context"
	"fmt"
	"math"
	"time"

	"go.chromium.org/luci/common/data/stringset"
)

// Scheduler encapsulates the state and configuration of a running
// quotascheduler for a single pool, and its methods provide an implementation
// of the quotascheduler algorithm.
type Scheduler struct {
	state  *state
	config *Config
}

// AccountID (a string) identifies an account.
type AccountID string

// WorkerID (a string) identifies a worker.
type WorkerID string

// RequestID (a string) identifies a request.
type RequestID string

// AssignmentType is an enum of scheduler assignment types.
type AssignmentType int

const (
	// AssignmentIdleWorker indicates assigning a task to a currently idle worker.
	AssignmentIdleWorker AssignmentType = iota

	// AssignmentPreemptWorker indicates preempting a running task on a worker with a new task.
	AssignmentPreemptWorker
)

// An Assignment represents a scheduler decision to assign a task to a worker.
type Assignment struct {
	// Type describes which kind of assignment this represents.
	Type AssignmentType

	// WorkerID of the worker to assign a new task to (and to preempt the previous
	// task of, if this is a AssignmentPreemptWorker mutator).
	WorkerID WorkerID

	// RequestID of the task to assign to that worker.
	RequestID RequestID

	// TaskToAbort is relevant only for the AssignmentPreemptWorker type.
	// It is the request ID of the task that should be preempted.
	TaskToAbort RequestID

	// Priority at which the task will run.
	Priority int

	// Time is the time at which this Assignment was determined.
	Time time.Time
}

// New returns a newly initialized Scheduler.
func New(t time.Time) *Scheduler {
	return &Scheduler{
		state:  newState(t),
		config: NewConfig(),
	}
}

// NewFromProto returns a new Scheduler from proto representation.
func NewFromProto(s *SchedulerProto) *Scheduler {
	return &Scheduler{newStateFromProto(s.State), s.Config}
}

// ToProto returns a proto representation of the state and configuration of Scheduler.
func (s *Scheduler) ToProto() *SchedulerProto {
	return &SchedulerProto{
		State:  s.state.toProto(),
		Config: s.config,
	}
}

// UpdateOrderError is an error that indicates that UpdateAccounts attempted to update a state
// backwards in time.
type UpdateOrderError struct {
	Previous time.Time
	Next     time.Time
}

// Error() implements the error interface.
func (e *UpdateOrderError) Error() string {
	return fmt.Sprintf("Update time %v was older than existing state's time %v.", e.Next, e.Previous)
}

// AddAccount creates a new account with the given id, config, and initialBalance
// (or zero balance if nil).
//
// If an account with that id already exists, then it is overwritten.
func (s *Scheduler) AddAccount(ctx context.Context, id AccountID, config *AccountConfig, initialBalance []float64) error {
	s.ensureMaps()
	s.config.AccountConfigs[string(id)] = config
	bal := balance{}
	copy(bal[:], initialBalance)
	s.state.balances[id] = bal
	return nil
}

// AddRequest enqueues a new task request.
func (s *Scheduler) AddRequest(ctx context.Context, requestID RequestID, request *TaskRequest, t time.Time) error {
	s.ensureMaps()
	s.state.addRequest(ctx, requestID, request, t)
	return nil
}

// IsAssigned returns whether the given request is currently assigned to the
// given worker. It is provided for a consistency checks.
func (s *Scheduler) IsAssigned(requestID RequestID, workerID WorkerID) bool {
	s.ensureMaps()
	if w, ok := s.state.workers[workerID]; ok {
		if !w.isIdle() {
			return w.runningTask.requestID == requestID
		}
	}
	return false
}

// UpdateTime updates the current time for a quotascheduler, and
// updates quota account balances accordingly, based on running jobs,
// account policies, and the time elapsed since the last update.
func (s *Scheduler) UpdateTime(ctx context.Context, t time.Time) error {
	s.ensureMaps()
	state := s.state
	config := s.config
	t0 := state.lastUpdateTime

	if t.Before(t0) {
		return &UpdateOrderError{Previous: t0, Next: t}
	}

	elapsedSecs := t.Sub(t0).Seconds()

	// Count the number of running tasks per priority bucket for each
	//
	// Since we are iterating over all running tasks, also use this
	// opportunity to update the accumulate cost of running tasks.
	jobsPerAcct := make(map[AccountID][]int)

	for _, w := range state.workers {
		if !w.isIdle() {
			id := w.runningTask.request.accountID
			c := jobsPerAcct[id]
			if c == nil {
				c = make([]int, NumPriorities)
				jobsPerAcct[id] = c
			}
			rt := w.runningTask
			p := rt.priority
			// Count running tasks unless they are in the FreeBucket (p = NumPriorities).
			if p < NumPriorities {
				c[w.runningTask.priority]++
				rt.cost[p] += elapsedSecs
			}
		}
	}

	// Determine the new account balance for each
	// TODO(akeshet): Update balance in-place rather than creating all new map.
	newBalances := make(map[AccountID]balance)
	for id, acct := range config.AccountConfigs {
		accountID := AccountID(id)
		before := state.balances[accountID]
		runningJobs := jobsPerAcct[accountID]
		if runningJobs == nil {
			runningJobs = make([]int, NumPriorities)
		}
		after := nextBalance(before, acct, elapsedSecs, runningJobs)
		newBalances[accountID] = after
	}
	state.balances = newBalances

	state.lastUpdateTime = t

	return nil
}

// IdleWorker describes a worker that is idle, along with
// the provisionable labels that it possesses.
type IdleWorker struct {
	WorkerID string
	Labels   stringset.Set
}

// MarkIdle marks the given worker as idle, and with the given provisionable,
// labels, as of the given time. If this call is contradicted by newer knowledge
// of state, then it does nothing.
//
// Note: calls to MarkIdle come from bot reap calls from swarming.
func (s *Scheduler) MarkIdle(ctx context.Context, workerID WorkerID, labels stringset.Set, t time.Time) error {
	s.ensureMaps()
	s.state.markIdle(workerID, labels, t)
	return nil
}

// NotifyRequest informs the scheduler authoritatively that the given request
// was running on the given worker (or was idle, for workerID = "") at the
// given time.
//
// Supplied requestID must not be "".
//
// Note: calls to NotifyRequest come from task update pubsub messages from swarming.
func (s *Scheduler) NotifyRequest(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time) error {
	s.ensureMaps()
	s.state.notifyRequest(ctx, requestID, workerID, t)
	return nil
}

// AbortRequest informs the scheduler authoritatively that the given request
// is stopped (not running on a worker, and not in the queue) at the given time.
//
// Supplied requestID must not be "".
func (s *Scheduler) AbortRequest(ctx context.Context, requestID RequestID, t time.Time) error {
	s.ensureMaps()
	s.state.abortRequest(ctx, requestID, t)
	return nil
}

// RunOnce performs a single round of the quota scheduler algorithm
// on a given state and config, and returns a slice of state mutations.
//
// TODO(akeshet): Revisit how to make this function an interruptable goroutine-based
// calculation.
func (s *Scheduler) RunOnce(ctx context.Context) ([]*Assignment, error) {
	s.ensureMaps()
	state := s.state
	config := s.config
	requests := s.prioritizeRequests()
	var output []*Assignment

	// Proceed through multiple passes of the scheduling algorithm, from highest
	// to lowest priority requests (high priority = low p).
	for p := int(0); p < NumPriorities; p++ {
		// TODO(akeshet): There are a number of ways to optimize this loop eventually.
		// For instance:
		// - Bail out if there are no more idle workers and no more
		//   running jobs beyond a given
		jobsAtP := requests.forPriority(p)
		// Step 1: Match any requests to idle workers that have matching
		// provisionable labels.
		output = append(output, matchIdleBotsWithLabels(state, jobsAtP)...)
		// Step 2: Match request to any remaining idle workers, regardless of
		// provisionable labels.
		output = append(output, matchIdleBots(state, jobsAtP)...)
		// Step 3: Demote (out of this level) or promote (into this level) any
		// already running tasks that qualify.
		reprioritizeRunningTasks(state, config, p)
		// Step 4: Preempt any lower priority running tasks.
		output = append(output, preemptRunningTasks(state, jobsAtP, p)...)
	}

	// A final pass matches free jobs (in the FreeBucket) to any remaining
	// idle workers. The reprioritize and preempt stages do not apply here.
	freeJobs := requests.forPriority(FreeBucket)
	output = append(output, matchIdleBotsWithLabels(state, freeJobs)...)
	output = append(output, matchIdleBots(state, freeJobs)...)

	return output, nil
}

// GetRequest returns the (waiting or running) request for a given ID.
func (s *Scheduler) GetRequest(rid RequestID) (req *TaskRequest, ok bool) {
	if r, ok := s.state.getRequest(rid); ok {
		return newTaskRequest(r), ok
	}
	return nil, false
}

// matchIdleBotsWithLabels matches requests with idle workers that already
// share all of that request's provisionable labels.
func matchIdleBotsWithLabels(s *state, requestsAtP orderedRequests) []*Assignment {
	var output []*Assignment
	for i, request := range requestsAtP {
		if request.Scheduled {
			// This should not be possible, because matching by label is the first
			// pass at a given priority label, so no requests should be already scheduled.
			// Nevertheless, handle it.
			continue
		}
		for wid, worker := range s.workers {
			if worker.isIdle() && worker.labels.Contains(request.Request.provisionableLabels) {
				m := &Assignment{
					Type:      AssignmentIdleWorker,
					WorkerID:  wid,
					RequestID: request.RequestID,
					Priority:  request.Priority,
					Time:      s.lastUpdateTime,
				}
				output = append(output, m)
				s.applyAssignment(m)
				requestsAtP[i] = prioritizedRequest{Scheduled: true}
				break
			}
		}
	}
	return output
}

// matchIdleBots matches requests with any idle workers.
func matchIdleBots(state *state, requestsAtP []prioritizedRequest) []*Assignment {
	var output []*Assignment

	// TODO(akeshet): Use maybeIdle to communicate back to caller that there is no need
	// to call matchIdleBots again, or to attempt FreeBucket scheduling.
	// Even though maybeIdle is unused, the logic to compute it is non-trivial
	// so leaving it in place and suppressing unused variable message.
	maybeIdle := false
	var _ = maybeIdle // Drop this once maybeIdle is used.

	idleWorkersIds := make([]WorkerID, 0, len(state.workers))
	for wid, worker := range state.workers {
		if worker.isIdle() {
			idleWorkersIds = append(idleWorkersIds, wid)
			maybeIdle = true
		}
	}

	for r, w := 0, 0; r < len(requestsAtP) && w < len(idleWorkersIds); r++ {
		request := requestsAtP[r]
		wid := idleWorkersIds[w]
		if request.Scheduled {
			// Skip this entry, it is already scheduled.
			continue
		}
		m := &Assignment{
			Type:      AssignmentIdleWorker,
			WorkerID:  wid,
			RequestID: request.RequestID,
			Priority:  request.Priority,
			Time:      state.lastUpdateTime,
		}
		output = append(output, m)
		state.applyAssignment(m)
		requestsAtP[r] = prioritizedRequest{Scheduled: true}
		w++
		if w == len(idleWorkersIds) {
			maybeIdle = false
		}
	}
	return output
}

// reprioritizeRunningTasks changes the priority of running tasks by either
// demoting jobs out of the given priority (from level p to level p + 1),
// or by promoting tasks (from any level > p to level p).
//
// Running tasks are demoted if their quota account has too negative a balance
// (Note: a given request may be demoted multiple times, in successive passes,
// from p -> p + 1 -> p + 2 etc if its account has negative balance in multiple
// priority buckets)
//
// Running tasks are promoted if their quota account has a sufficiently positive
// balance and a recharge rate that can sustain them at this level.
func reprioritizeRunningTasks(state *state, config *Config, priority int) {
	// TODO(akeshet): jobs that are currently running, but have no corresponding account,
	// should be demoted immediately to the FreeBucket (probably their account
	// was deleted while running).
	for accountID, fullBalance := range state.balances {
		// TODO(akeshet): move the body of this loop to own function.
		accountConfig, ok := config.AccountConfigs[string(accountID)]
		if !ok {
			panic(fmt.Sprintf("There was a balance for unknown account %s", accountID))
		}
		balance := fullBalance[priority]
		demote := balance < DemoteThreshold
		promote := balance > PromoteThreshold
		if !demote && !promote {
			continue
		}

		runningAtP := workersAt(state.workers, priority, accountID)

		chargeRate := accountConfig.ChargeRate[priority] - float64(len(runningAtP))

		switch {
		case demote && chargeRate < 0:
			doDemote(state, runningAtP, chargeRate, priority)
		case promote && chargeRate > 0:
			runningBelowP := workersBelow(state.workers, priority, accountID)
			doPromote(state, runningBelowP, chargeRate, priority)
		}
	}
}

// TODO(akeshet): Consider unifying doDemote and doPromote somewhat
// to reuse more code.

// doDemote is a helper function used by reprioritizeRunningTasks
// which demotes some jobs (selected from candidates) from priority to priority + 1.
func doDemote(state *state, candidates []workerWithID, chargeRate float64, priority int) {
	sortAscendingCost(candidates)

	numberToDemote := minInt(len(candidates), int(math.Ceil(-chargeRate)))
	for _, toDemote := range candidates[:numberToDemote] {
		toDemote.worker.runningTask.priority = priority + 1
	}
}

// doPromote is a helper function use by reprioritizeRunningTasks
// which promotes some jobs (selected from candidates) from any level > priority
// to priority.
func doPromote(state *state, candidates []workerWithID, chargeRate float64, priority int) {
	sortDescendingCost(candidates)

	numberToPromote := minInt(len(candidates), int(math.Ceil(chargeRate)))
	for _, toPromote := range candidates[:numberToPromote] {
		toPromote.worker.runningTask.priority = priority
	}
}

// workersAt is a helper function that returns the workers with a given
// account id and running.
func workersAt(ws map[WorkerID]*worker, priority int, accountID AccountID) []workerWithID {
	ans := make([]workerWithID, 0, len(ws))
	for wid, worker := range ws {
		if !worker.isIdle() &&
			worker.runningTask.request.accountID == accountID &&
			worker.runningTask.priority == priority {
			ans = append(ans, workerWithID{worker, wid})
		}
	}
	return ans
}

// workersBelow is a helper function that returns the workers with a given
// account id and below a given running.
func workersBelow(ws map[WorkerID]*worker, priority int, accountID AccountID) []workerWithID {
	ans := make([]workerWithID, 0, len(ws))
	for wid, worker := range ws {
		if !worker.isIdle() &&
			worker.runningTask.request.accountID == accountID &&
			worker.runningTask.priority > priority {
			ans = append(ans, workerWithID{worker, wid})
		}
	}
	return ans
}

// preemptRunningTasks interrupts lower priority already-running tasks, and
// replaces them with higher priority tasks. When doing so, it also reimburses
// the account that had been charged for the task.
func preemptRunningTasks(state *state, jobsAtP []prioritizedRequest, priority int) []*Assignment {
	var output []*Assignment
	candidates := make([]workerWithID, 0, len(state.workers))
	// Accounts that are already running a lower priority job are not
	// permitted to preempt jobs at this priority. This is to prevent a type
	// of thrashing that may occur if an account is unable to promote jobs to
	// this priority (because that would push it over its charge rate)
	// but still has positive quota at this priority.
	bannedAccounts := make(map[AccountID]bool)
	for wid, worker := range state.workers {
		if !worker.isIdle() && worker.runningTask.priority > priority {
			candidates = append(candidates, workerWithID{worker, wid})
			bannedAccounts[worker.runningTask.request.accountID] = true
		}
	}

	sortAscendingCost(candidates)

	for rI, cI := 0, 0; rI < len(jobsAtP) && cI < len(candidates); rI++ {
		request := jobsAtP[rI]
		candidate := candidates[cI]
		if request.Scheduled {
			continue
		}
		requestAccountID := request.Request.accountID
		if _, ok := bannedAccounts[requestAccountID]; ok {
			continue
		}
		cost := candidate.worker.runningTask.cost
		requestAccountBalance, ok := state.balances[requestAccountID]
		if !ok || less(requestAccountBalance, cost) {
			continue
		}
		mut := &Assignment{
			Type:        AssignmentPreemptWorker,
			Priority:    priority,
			RequestID:   request.RequestID,
			TaskToAbort: candidate.worker.runningTask.requestID,
			WorkerID:    candidate.id,
			Time:        state.lastUpdateTime,
		}
		output = append(output, mut)
		state.applyAssignment(mut)
		request.Scheduled = true
		cI++
	}
	return output
}

// ensureMaps ensures that all maps in scheduler or its child structs are
// non-nil, and initializes them otherwise.
//
// This is necessary because protobuf deserialization of an empty map returns a nil map.
// TODO(akeshet): After the proto-decoupling refactor is completed, remove this method.
func (s *Scheduler) ensureMaps() {
	if s.config.AccountConfigs == nil {
		s.config.AccountConfigs = make(map[string]*AccountConfig)
	}
	if s.state.balances == nil {
		s.state.balances = make(map[AccountID]balance)
	}
	if s.state.queuedRequests == nil {
		s.state.queuedRequests = make(map[RequestID]*request)
	}
	if s.state.workers == nil {
		s.state.workers = make(map[WorkerID]*worker)
	}
}

// minInt returns the lesser of two integers.
func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
