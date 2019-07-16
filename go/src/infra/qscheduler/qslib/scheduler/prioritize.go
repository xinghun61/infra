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
)

// prioritizeRequests computes the priority of requests from state.Requests.
//
// The computed priority is based on:
//   - Quota account balances: requests are assigned a priority based on what
//     buckets their account has positive balance for.
//   - Max fanout: for any given account, if there are more than the max fanout
//     number of requests already running, requests for that account will be
//     deprioritized to the FreeBucket.
//
// Within a priority bucket, items are sorted in ascending examinedTime order.
//
// This function does not modify state or config.
func (s *Scheduler) prioritizeRequests(fanoutCounter *fanoutCounter) [NumPriorities + 1]requestList {
	state := s.state

	var prioritized [NumPriorities + 1]requestList

	for _, req := range state.queuedRequests {
		if req.ID == "" {
			panic("empty request ID")
		}
		var p Priority
		if fanoutCounter.getRemaining(req) <= 0 {
			p = FreeBucket
		} else {
			p = BestPriorityFor(state.balances[req.AccountID])
		}

		disableIfFree := false
		if c, ok := s.config.AccountConfigs[string(req.AccountID)]; ok {
			disableIfFree = c.DisableFreeTasks
		}

		if p == FreeBucket && disableIfFree {
			// Free tasks from accounts with this flag have no chance of matching,
			// omit them from scheduling.
			continue
		}

		prioritized[p] = append(prioritized[p], &requestListItem{
			req:           req,
			matched:       false,
			disableIfFree: disableIfFree,
		})
	}

	for _, p := range prioritized {
		sort.Sort(p)
	}

	return prioritized
}
