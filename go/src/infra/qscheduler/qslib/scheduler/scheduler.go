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

// Package scheduler provides Scheduler, which is an implementation of
// the quotascheduler algorithm.
//
// TODO(akeshet): Describe a story around the main calls that scheduler exposes,
// and implement a few remaining ones. They will be things like:
//  - Get/Set Config
//  - InsertTask
//  - UpdateTime
//  - ReapFor
package scheduler

import (
	"fmt"
	"math"
	"time"

	"github.com/golang/protobuf/ptypes"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// TODO(akeshet): Move all public API calls for scheduler to their own
// file.
// TODO(akeshet): Add unit test around the public API calls.

// Scheduler encapsulates the state of a running quotascheduler, and its method
// provide an implementation of the quotascheduler algorithm.
type Scheduler struct {
	state  *State
	config *Config
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

// UpdateTime updates the current time for a quotascheduler, and
// updates quota account balances accordingly, based on running jobs,
// account policies, and the time elapsed since the last update.
func (s *Scheduler) UpdateTime(t time.Time) error {
	state := s.state
	config := s.config
	t0, err := ptypes.Timestamp(state.LastUpdateTime)
	if err != nil {
		return err
	}

	if t0.After(t) {
		return &UpdateOrderError{Previous: t0, Next: t}
	}

	elapsedSecs := t.Sub(t0).Seconds()

	// Count the number of running tasks per priority bucket for each account.
	//
	// Since we are iterating over all running tasks, also use this
	// opportunity to update the accumulate cost of running tasks.
	jobsPerAcct := make(map[string]*vector.IntVector)
	if state.Workers != nil {
		for _, w := range state.Workers {
			if !w.isIdle() {
				id := w.RunningTask.Request.AccountId
				c := jobsPerAcct[id]
				if c == nil {
					c = &vector.IntVector{}
					jobsPerAcct[id] = c
				}
				rt := w.RunningTask
				if rt.Cost == nil {
					rt.Cost = vector.New()
				}
				p := rt.Priority
				// Count running tasks unless they are in the FreeBucket (p = NumPriorities).
				if p < vector.NumPriorities {
					c[w.RunningTask.Priority]++
					rt.Cost.Values[p] += elapsedSecs
				}
			}
		}
	}

	// Determine the new account balance for each account.
	newBalances := make(map[string]*vector.Vector)
	for id, acct := range config.AccountConfigs {
		before := state.Balances[id]
		if before == nil {
			before = vector.New()
		}
		runningJobs := jobsPerAcct[id]
		if runningJobs == nil {
			runningJobs = &vector.IntVector{}
		}
		after := account.NextBalance(before, acct, elapsedSecs, runningJobs)
		newBalances[id] = after
	}
	state.Balances = newBalances

	state.LastUpdateTime = tutils.TimestampProto(t)

	return nil
}

// IdleWorker describes a worker that is idle, along with
// the provisionable labels that it possesses.
type IdleWorker struct {
	WorkerId string
	Labels   task.LabelSet
}

// MarkIdle marks the given worker as idle, and with
// the given provisionable labels.
func (s *Scheduler) MarkIdle(id string, labels task.LabelSet) {
	s.state.Workers[id] = &Worker{Labels: labels}
}

// RunOnce performs a single round of the quota scheduler algorithm
// on a given state and config, and returns a slice of state mutations.
//
// TODO(akeshet): Revisit how to make this function an interruptable goroutine-based
// calculation.
func (s *Scheduler) RunOnce() []*Assignment {
	state := s.state
	config := s.config
	requests := s.prioritizeRequests()
	var output []*Assignment

	// Proceed through multiple passes of the scheduling algorithm, from highest
	// to lowest priority requests (high priority = low p).
	for p := int32(0); p < vector.NumPriorities; p++ {
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
	freeJobs := requests.forPriority(account.FreeBucket)
	output = append(output, matchIdleBotsWithLabels(state, freeJobs)...)
	output = append(output, matchIdleBots(state, freeJobs)...)

	return output
}

// matchIdleBotsWithLabels matches requests with idle workers that already
// share all of that request's provisionable labels.
func matchIdleBotsWithLabels(state *State, requestsAtP orderedRequests) []*Assignment {
	var output []*Assignment
	for i, request := range requestsAtP {
		if request.Scheduled {
			// This should not be possible, because matching by label is the first
			// pass at a given priority label, so no requests should be already scheduled.
			// Nevertheless, handle it.
			continue
		}
		for wid, worker := range state.Workers {
			if worker.isIdle() && task.LabelSet(worker.Labels).Equal(request.Request.Labels) {
				m := &Assignment{
					Type:      Assignment_IDLE_WORKER,
					WorkerId:  wid,
					RequestId: request.RequestId,
					Priority:  request.Priority,
				}
				output = append(output, m)
				m.apply(state)
				requestsAtP[i] = prioritizedRequest{Scheduled: true}
				break
			}
		}
	}
	return output
}

// matchIdleBots matches requests with any idle workers.
func matchIdleBots(state *State, requestsAtP []prioritizedRequest) []*Assignment {
	var output []*Assignment

	// TODO(akeshet): Use maybeIdle to communicate back to caller that there is no need
	// to call matchIdleBots again, or to attempt FreeBucket scheduling.
	// Even though maybeIdle is unused, the logic to compute it is non-trivial
	// so leaving it in place and suppressing unused variable message.
	maybeIdle := false
	var _ = maybeIdle // Drop this once maybeIdle is used.

	idleWorkersIds := make([]string, 0, len(state.Workers))
	for wid, worker := range state.Workers {
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
			Type:      Assignment_IDLE_WORKER,
			WorkerId:  wid,
			RequestId: request.RequestId,
			Priority:  request.Priority,
		}
		output = append(output, m)
		m.apply(state)
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
func reprioritizeRunningTasks(state *State, config *Config, priority int32) {
	// TODO(akeshet): jobs that are currently running, but have no corresponding account,
	// should be demoted immediately to the FreeBucket (probably their account
	// was deleted while running).
	for accountID, fullBalance := range state.Balances {
		// TODO(akeshet): move the body of this loop to own function.
		accountConfig, ok := config.AccountConfigs[accountID]
		if !ok {
			panic(fmt.Sprintf("There was a balance for unknown account %s", accountID))
		}
		balance := fullBalance.At(priority)
		demote := balance < account.DemoteThreshold
		promote := balance > account.PromoteThreshold
		if !demote && !promote {
			continue
		}

		runningAtP := workersAt(state.Workers, priority, accountID)

		chargeRate := accountConfig.ChargeRate.At(priority) - float64(len(runningAtP))

		switch {
		case demote && chargeRate < 0:
			doDemote(state, runningAtP, chargeRate, priority)
		case promote && chargeRate > 0:
			runningBelowP := workersBelow(state.Workers, priority, accountID)
			doPromote(state, runningBelowP, chargeRate, priority)
		}
	}
}

// TODO(akeshet): Consider unifying doDemote and doPromote somewhat
// to reuse more code.

// doDemote is a helper function used by reprioritizeRunningTasks
// which demotes some jobs (selected from candidates) from priority to priority + 1.
func doDemote(state *State, candidates []workerWithId, chargeRate float64, priority int32) {
	sortAscendingCost(candidates)

	numberToDemote := minInt(len(candidates), int(math.Ceil(-chargeRate)))
	for _, toDemote := range candidates[:numberToDemote] {
		toDemote.worker.RunningTask.Priority = priority + 1
	}
}

// doPromote is a helper function use by reprioritizeRunningTasks
// which promotes some jobs (selected from candidates) from any level > priority
// to priority.
func doPromote(state *State, candidates []workerWithId, chargeRate float64, priority int32) {
	sortDescendingCost(candidates)

	numberToPromote := minInt(len(candidates), int(math.Ceil(chargeRate)))
	for _, toPromote := range candidates[:numberToPromote] {
		toPromote.worker.RunningTask.Priority = priority
	}
}

// workersAt is a helper function that returns the workers with a given
// account id and running.
func workersAt(ws map[string]*Worker, priority int32, accountID string) []workerWithId {
	ans := make([]workerWithId, 0, len(ws))
	for wid, worker := range ws {
		if !worker.isIdle() &&
			worker.RunningTask.Request.AccountId == accountID &&
			worker.RunningTask.Priority == priority {
			ans = append(ans, workerWithId{worker, wid})
		}
	}
	return ans
}

// workersBelow is a helper function that returns the workers with a given
// account id and below a given running.
func workersBelow(ws map[string]*Worker, priority int32, accountID string) []workerWithId {
	ans := make([]workerWithId, 0, len(ws))
	for wid, worker := range ws {
		if !worker.isIdle() &&
			worker.RunningTask.Request.AccountId == accountID &&
			worker.RunningTask.Priority > priority {
			ans = append(ans, workerWithId{worker, wid})
		}
	}
	return ans
}

// preemptRunningTasks interrupts lower priority already-running tasks, and
// replaces them with higher priority tasks. When doing so, it also reimburses
// the account that had been charged for the task.
func preemptRunningTasks(state *State, jobsAtP []prioritizedRequest, priority int32) []*Assignment {
	var output []*Assignment
	candidates := make([]workerWithId, 0, len(state.Workers))
	// Accounts that are already running a lower priority job are not
	// permitted to preempt jobs at this priority. This is to prevent a type
	// of thrashing that may occur if an account is unable to promote jobs to
	// this priority (because that would push it over its charge rate)
	// but still has positive quota at this priority.
	bannedAccounts := make(map[string]bool)
	for wid, worker := range state.Workers {
		if !worker.isIdle() && worker.RunningTask.Priority > priority {
			candidates = append(candidates, workerWithId{worker, wid})
			bannedAccounts[worker.RunningTask.Request.AccountId] = true
		}
	}

	sortAscendingCost(candidates)

	for rI, cI := 0, 0; rI < len(jobsAtP) && cI < len(candidates); rI++ {
		request := jobsAtP[rI]
		candidate := candidates[cI]
		if request.Scheduled {
			continue
		}
		requestAccountID := request.Request.AccountId
		if _, ok := bannedAccounts[requestAccountID]; ok {
			continue
		}
		cost := candidate.worker.RunningTask.Cost
		requestAccountBalance, ok := state.Balances[requestAccountID]
		if !ok || requestAccountBalance.Less(*cost) {
			continue
		}
		mut := &Assignment{Type: Assignment_PREEMPT_WORKER, Priority: priority, RequestId: request.RequestId, WorkerId: candidate.id}
		output = append(output, mut)
		mut.apply(state)
		request.Scheduled = true
		cI++
	}
	return output
}

// minInt returns the lesser of two integers.
func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
