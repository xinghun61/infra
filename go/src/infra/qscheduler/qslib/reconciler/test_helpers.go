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

package reconciler

import (
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/task"
)

// fakeScheduler is an implementation of the Scheduler interface which makes
// assignments according to whatever is provided by MockSchedule.
type fakeScheduler struct {
	// assignments is a map from worker ID to the scheduler.Assignment that will
	// be reaped for that worker.
	assignments map[string]*scheduler.Assignment

	// idleWorkers is the set of workers that have been marked as idle and have
	// not yet had any assignments scheduled / reaped for them
	idleWorkers map[string]bool
}

// UpdateTime is an implmementation of the Scheduler interface.
func (s *fakeScheduler) UpdateTime(t time.Time) error {
	return nil
}

// MarkIdle is an implementation of the Scheduler interface.
func (s *fakeScheduler) MarkIdle(id string, labels task.LabelSet) {
	s.idleWorkers[id] = true
}

// RunOnce is an implementation of the Scheduler interface.
func (s *fakeScheduler) RunOnce() []*scheduler.Assignment {
	response := make([]*scheduler.Assignment, 0, len(s.idleWorkers))
	for worker := range s.idleWorkers {
		if match, ok := s.assignments[worker]; ok {
			response = append(response, match)
			delete(s.assignments, worker)
			delete(s.idleWorkers, worker)
		}
	}
	return response
}

// AddRequest is an implementation of the Scheduler interface.
func (s *fakeScheduler) AddRequest(id string, request *task.Request) {}

// fakeSchedule sets the given assignment in a fakeScheduler.
func (s *fakeScheduler) fakeSchedule(a *scheduler.Assignment) {
	s.assignments[a.WorkerId] = a
}

// newFakeScheduler returns a new initialized mock scheduler.
func newFakeScheduler() *fakeScheduler {
	return &fakeScheduler{
		assignments: make(map[string]*scheduler.Assignment),
		idleWorkers: make(map[string]bool),
	}
}

// fifoScheduler is an implementation of the Scheduler interface that
// schedules requests in a simple FIFO order, ignoring accounts or
// provisionable label matching, and performing no preemptions.
type fifoScheduler struct {
	queueIDs    []string
	idleWorkers []string
	t           time.Time
}

// UpdateTime is an implementation of the Scheduler interface.
func (s *fifoScheduler) UpdateTime(t time.Time) error {
	s.t = t
	return nil
}

// MarkIdle is an implementation of the Scheduler interface.
func (s *fifoScheduler) MarkIdle(id string, labels task.LabelSet) {
	for _, idle := range s.idleWorkers {
		if idle == id {
			return
		}
	}
	s.idleWorkers = append(s.idleWorkers, id)
}

// RunOnce is an implementation of the Scheduler interface.
func (s *fifoScheduler) RunOnce() []*scheduler.Assignment {
	idles := len(s.idleWorkers)
	requests := len(s.queueIDs)

	matches := idles
	if requests < matches {
		matches = requests
	}

	response := make([]*scheduler.Assignment, matches)

	for i := 0; i < matches; i++ {
		response[i] = &scheduler.Assignment{
			RequestId: s.queueIDs[0],
			WorkerId:  s.idleWorkers[0],
			Time:      tutils.TimestampProto(s.t),
		}
		s.queueIDs = s.queueIDs[1:]
		s.idleWorkers = s.idleWorkers[1:]
	}

	return response
}

// AddRequest is an implementation of the Scheduler interface.
func (s *fifoScheduler) AddRequest(id string, request *task.Request) {
	s.queueIDs = append(s.queueIDs, id)
}
