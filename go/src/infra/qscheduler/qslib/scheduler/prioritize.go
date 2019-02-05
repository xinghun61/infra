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
	"container/list"
	"sort"
)

// requestList is a wrapper around container/list.List that is type safe as a linked list of
// *request valued nodes.
type requestList struct {
	*list.List
}

// requestNode is a wrapper around container/list.Element that is type safe as a *request valued
// node.
type requestNode struct {
	*list.Element
}

func (r *requestList) Head() requestNode {
	elem := r.Front()
	return requestNode{elem}
}

func (r *requestList) PushBack(req *TaskRequest) requestNode {
	return requestNode{r.List.PushBack(req)}
}

func (n requestNode) Value() *TaskRequest {
	return n.Element.Value.(*TaskRequest)
}

func (n requestNode) Next() requestNode {
	elem := n.Element.Next()
	return requestNode{elem}
}

// prioritizeRequests computes the priority of requests from state.Requests.
//
// The computed priority is based on:
//   - Quota account balances: requests are assigned a priority based on what
//     buckets their account has positive balance for.
//   - Max fanout: for any given account, if there are more than the max fanout
//     number of requests already running, requests for that account will be
//     deprioritized to the FreeBucket.
//   - FIFO ordering as a tiebreaker.
//
// This function does not modify state or config.
func (s *Scheduler) prioritizeRequests(jobsUntilThrottled map[AccountID]int) [NumPriorities + 1]requestList {
	state := s.state

	var prioritized [NumPriorities + 1][]*TaskRequest
	// Preallocate slices at each priority level to avoid the need for any resizing later.
	for i := range prioritized {
		prioritized[i] = make([]*TaskRequest, 0, len(s.state.queuedRequests))
	}

	for _, req := range state.queuedRequests {
		if req.ID == "" {
			panic("empty request ID")
		}
		var p Priority
		if jobsUntilThrottled[req.AccountID] <= 0 {
			p = FreeBucket
		} else {
			p = BestPriorityFor(state.balances[req.AccountID])
		}

		prioritized[p] = append(prioritized[p], req)
	}

	var output [NumPriorities + 1]requestList
	for priority, p := range prioritized {
		output[priority] = requestList{&list.List{}}
		sort.SliceStable(p, func(i, j int) bool {
			return p[i].EnqueueTime.Before(p[j].EnqueueTime)
		})
		for _, r := range p {
			output[priority].PushBack(r)
		}
	}

	return output
}
