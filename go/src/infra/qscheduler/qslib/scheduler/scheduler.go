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
	"math"

	"infra/qscheduler/qslib/mutaters"
	"infra/qscheduler/qslib/priority"
	"infra/qscheduler/qslib/types"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// QuotaSchedule performs a single round of the quota scheduler algorithm
// on a given state and config, and returns a slice of state mutations.
//
// TODO: Revisit how to make this function an interruptable goroutine-based
// calculation.
func QuotaSchedule(state *types.State, config *types.Config) []mutaters.Mutater {
	var output []mutaters.Mutater
	requests := priority.PrioritizeRequests(state, config)

	// Proceed through multiple passes of the scheduling algorithm, from highest
	// to lowest priority requests (high priority = low p).
	for p := int32(0); p < vector.NumPriorities; p++ {
		// TODO: There are a number of ways to optimize this loop eventually.
		// For instance:
		// - Bail out if there are no more idle workers and no more
		//   running jobs beyond a given priority.
		jobsAtP := requests.ForPriority(p)
		// Step 1: Match any requests to idle workers that have matching
		// provisionable labels.
		output = append(output, matchIdleBotsWithLabels(state, jobsAtP)...)
		// Step 2: Match request to any remaining idle workers, regardless of
		// provisionable labels.
		output = append(output, matchIdleBots(state, jobsAtP)...)
		// Step 3: Demote (out of this level) or promote (into this level) any
		// already running tasks that qualify.
		output = append(output, reprioritizeRunningTasks(state, config, p)...)
		// Step 4: Preempt any lower priority running tasks.
		output = append(output, preemptRunningTasks(state, jobsAtP, p)...)
	}

	// A final pass matches free jobs (in the FreeBucket) to any remaining
	// idle workers. The reprioritize and preempt stages do not apply here.
	freeJobs := requests.ForPriority(account.FreeBucket)
	output = append(output, matchIdleBotsWithLabels(state, freeJobs)...)
	output = append(output, matchIdleBots(state, freeJobs)...)

	return output
}

// matchIdleBotsWithLabels matches requests with idle workers that already
// share all of that request's provisionable labels.
func matchIdleBotsWithLabels(state *types.State, requestsAtP priority.OrderedRequests) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)
	for i, request := range requestsAtP {
		if request.Scheduled {
			continue
		}
		for _, worker := range state.Workers {
			if worker.IsIdle() && task.LabelSet(worker.Labels).Equal(request.Request.Labels) {
				m := mutaters.AssignIdleWorker{
					WorkerId:  worker.Id,
					RequestId: request.Request.Id,
					Priority:  request.Priority,
				}
				output = append(output, &m)
				m.Mutate(state)
				requestsAtP[i] = priority.Request{Scheduled: true}
				break
			}
		}
	}
	return output
}

// matchIdleBots matches requests with any idle workers.
// Returns true if any job was matched.
func matchIdleBots(state *types.State, requestsAtP []priority.Request) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)

	// TODO: Use maybeIdle to communicate back to caller that there is no need
	// to call matchIdleBots again, or to attempt FreeBucket scheduling.
	// Even though maybeIdle is unused, the logic to compute it is non-trivial
	// so leaving it in place and suppressing unused variable message.
	maybeIdle := false
	var _ = maybeIdle // Drop this once maybeIdle is used.

	idleWorkers := make([]*types.Worker, 0, len(state.Workers))
	for _, worker := range state.Workers {
		if worker.IsIdle() {
			idleWorkers = append(idleWorkers, worker)
			maybeIdle = true
		}
	}

	for r, w := 0, 0; r < len(requestsAtP) && w < len(idleWorkers); r++ {
		request := requestsAtP[r]
		worker := idleWorkers[w]
		if request.Scheduled {
			// Skip this entry, it is already scheduled.
			continue
		}
		m := mutaters.AssignIdleWorker{
			WorkerId:  worker.Id,
			RequestId: request.Request.Id,
			Priority:  request.Priority,
		}
		output = append(output, &m)
		m.Mutate(state)
		requestsAtP[r] = priority.Request{Scheduled: true}
		w++
		if w == len(idleWorkers) {
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
func reprioritizeRunningTasks(state *types.State, config *types.Config, priority int32) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)
	// TODO: jobs that are currently running, but have no corresponding account,
	// should be demoted immediately to the FreeBucket (probably their account)
	// was deleted while running.
	for accountID, fullBalance := range state.Balances {
		// TODO: move the body of this loop to own function.
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
			output = append(output, doDemote(state, runningAtP, chargeRate, priority)...)
		case promote && chargeRate > 0:
			runningBelowP := workersBelow(state.Workers, priority, accountID)
			output = append(output, doPromote(state, runningBelowP, chargeRate, priority)...)
		}
	}
	return output
}

// TODO: Consider unifying doDemote and doPromote somewhat
// to reuse more code.

// doDemote is a helper function used by reprioritizeRunningTasks
// which demotes some jobs (selected from candidates) from priority to priority + 1.
func doDemote(state *types.State, candidates []*types.Worker, chargeRate float64, priority int32) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)
	types.SortAscendingCost(candidates)

	numberToDemote := minInt(len(candidates), int(math.Ceil(-chargeRate)))
	for _, toDemote := range candidates[:numberToDemote] {
		mut := &mutaters.ChangePriority{
			NewPriority: priority + 1,
			WorkerId:    toDemote.Id,
		}
		output = append(output, mut)
		mut.Mutate(state)
	}
	return output
}

// doPromote is a helper function use by reprioritizeRunningTasks
// which promotes some jobs (selected from candidates) from any level
// > priority to priority.
func doPromote(state *types.State, candidates []*types.Worker, chargeRate float64, priority int32) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)
	// We sort here in decreasing cost order.
	types.SortDescendingCost(candidates)

	numberToPromote := minInt(len(candidates), int(math.Ceil(chargeRate)))

	for _, toPromote := range candidates[:numberToPromote] {
		mut := &mutaters.ChangePriority{
			NewPriority: priority,
			WorkerId:    toPromote.Id,
		}
		output = append(output, mut)
		mut.Mutate(state)
	}
	return output
}

// workersAt is a helper function that returns the workers with a given
// account id and running priority.
func workersAt(ws map[string]*types.Worker, priority int32, accountID string) []*types.Worker {
	ans := make([]*types.Worker, 0, len(ws))
	for _, worker := range ws {
		if !worker.IsIdle() &&
			worker.RunningTask.Request.AccountId == accountID &&
			worker.RunningTask.Priority == priority {
			ans = append(ans, worker)
		}
	}
	return ans
}

// workersBelow is a helper function that returns the workers with a given
// account id and below a given running priority.
func workersBelow(ws map[string]*types.Worker, priority int32, accountID string) []*types.Worker {
	ans := make([]*types.Worker, 0, len(ws))
	for _, worker := range ws {
		if !worker.IsIdle() &&
			worker.RunningTask.Request.AccountId == accountID &&
			worker.RunningTask.Priority > priority {
			ans = append(ans, worker)
		}
	}
	return ans
}

// preemptRunningTasks interrupts lower priority already-running tasks, and
// replaces them with higher priority tasks. When doing so, it also reimburses
// the account that had been charged for the task.
func preemptRunningTasks(state *types.State, jobsAtP []priority.Request, priority int32) []mutaters.Mutater {
	output := make([]mutaters.Mutater, 0)
	candidates := make([]*types.Worker, 0, len(state.Workers))
	// Accounts that are already running a lower priority job are not
	// permitted to preempt jobs at this priority. This is to prevent a type
	// of thrashing that may occur if an account is unable to promote jobs to
	// this priority (because that would push it over its charge rate)
	// but still has positive quota at this priority.
	bannedAccounts := make(map[string]bool)
	for _, worker := range state.Workers {
		if !worker.IsIdle() && worker.RunningTask.Priority > priority {
			candidates = append(candidates, worker)
			bannedAccounts[worker.RunningTask.Request.AccountId] = true
		}
	}

	types.SortAscendingCost(candidates)

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
		cost := candidate.RunningTask.Cost
		requestAccountBalance, ok := state.Balances[requestAccountID]
		if !ok || requestAccountBalance.Less(*cost) {
			continue
		}
		mut := mutaters.PreemptTask{Priority: priority, RequestId: request.Request.Id, WorkerId: candidate.Id}
		output = append(output, &mut)
		mut.Mutate(state)
		request.Scheduled = true
		cI++
	}
	return output
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
