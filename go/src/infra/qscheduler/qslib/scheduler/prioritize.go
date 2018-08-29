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
	"sort"

	"github.com/golang/protobuf/ptypes"

	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
)

// prioritizedRequest represents a request along with the computed priority
// for it (based on quota account balance, max fanout for that account, and
// FIFO ordering).
type prioritizedRequest struct {
	RequestId string
	Priority  int32
	Request   *task.Request
	// Flag used within scheduler to indicate that a request is already handled.
	Scheduled bool
}

// orderedRequests represents a priority-sorted slice of requests.
type orderedRequests []prioritizedRequest

// prioritizeRequests computes the priority of requests from state.Requests.
//
// The computed priority is based on:
//   - Quota account balances: requests are assigned a priority based on what
//     buckets their account has positive balance for.
//   - Max fanout: for any given account, if there are more than the max fanout
//     number of running or higher-priority enqueued jobs, then further jobs
//     will be deprioritized to the FreeBucket.
//   - FIFO ordering as a tiebreaker.
//
// This function does not modify state or config.
func (s *Scheduler) prioritizeRequests() orderedRequests {
	state := s.state
	config := s.config
	// TODO Use container/heap rather than slices to make this faster.

	// Initial pass: compute priority for each task based purely on account
	// balance.
	requests := make(orderedRequests, 0, len(state.Requests))
	for id, req := range state.Requests {
		accoutBalance := state.Balances[req.AccountId]
		p := account.BestPriorityFor(accoutBalance)
		requests = append(requests, prioritizedRequest{
			Priority:  p,
			Request:   req,
			RequestId: id,
		})
	}

	less := func(i, j int) bool { return requestsLess(requests[i], requests[j]) }

	// Sort requests by priority, then demote in priority those that are beyond
	// an account's MaxFanout (because we want to demote the lowest priority jobs
	// that we can), and sort again.
	// TODO(akeshet): Use a heap instead of a slice here, then use heap fix when demoting
	// a job to avoid needing to re sort the full list.
	sort.SliceStable(requests, less)
	demoteTasksBeyondFanout(requests, state, config)
	sort.SliceStable(requests, less)
	return requests
}

// requestsLess is a helper function used when sorting prioritized requests
//
// It compares items at index i and j, using first their priority, then
// their enqueue time as tiebreaker.
func requestsLess(a, b prioritizedRequest) bool {
	if a.Priority == b.Priority {
		// Tiebreaker: enqueue time.
		// Ignore unlikely timestamp parsing error.
		timeA, _ := ptypes.Timestamp(a.Request.EnqueueTime)
		timeB, _ := ptypes.Timestamp(b.Request.EnqueueTime)
		return timeA.Before(timeB)
	}
	return a.Priority < b.Priority
}

// forPriority takes an already sorted prioritizedRequests slice, and
// returns the sub slice of it for the given priority
// TODO(akeshet): Consider turning this into a generator, so that it can iterate only
// once through the list rather than once per priority level.
func (s orderedRequests) forPriority(priority int32) orderedRequests {
	start := sort.Search(len(s), func(i int) bool { return s[i].Priority >= priority })
	end := sort.Search(len(s), func(i int) bool { return s[i].Priority > priority })
	return s[start:end]
}

// demoteTasksBeyondFanout enforces that no account will have more than that
// account's MaxFanout tasks running concurrently (aside from in the
// FreeBucket).
//
// TODO(akeshet): Possible optimizations:
//   - Pass in a heap instead of a sorted slice, and when demoting a job, demote
//     it and heap fix it. Rather than modify the slice and re-sort. This should
//     be a bit faster, because this function is likely to only demote a
//     fraction of jobs in the slice.
func demoteTasksBeyondFanout(prioritizedRequests orderedRequests, state *State, config *Config) {
	tasksPerAccount := make(map[string]int32)
	for _, w := range state.Workers {
		if !w.isIdle() {
			tasksPerAccount[w.RunningTask.Request.AccountId]++
		}
	}

	for i, r := range prioritizedRequests {
		id := r.Request.AccountId
		// Jobs without a valid account id / config are already assigned
		// to the free bucket, so ignore them here.
		if c, ok := config.AccountConfigs[id]; ok {
			if c.MaxFanout > 0 && tasksPerAccount[id] >= c.MaxFanout {
				prioritizedRequests[i].Priority = account.FreeBucket
			}
			tasksPerAccount[id]++
		}
	}
}
