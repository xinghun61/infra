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

package scheduler_test

import (
	"context"
	"fmt"
	"time"

	"infra/qscheduler/qslib/scheduler"

	"go.chromium.org/luci/common/data/stringset"
)

func HandleAssignments([]*scheduler.Assignment) {}

func IsOn(requestID scheduler.RequestID, workerID scheduler.WorkerID, s *scheduler.Scheduler) {
	fmt.Printf("%s is on %s? %v\n", requestID, workerID, s.IsAssigned(requestID, workerID))
}

func Example() {
	ctx := context.Background()

	// Create a scheduler.
	s := scheduler.New(time.Now())

	// Create a quota account with no initial balance.
	accountConfig := scheduler.NewAccountConfig(0, 1, []float64{1, 2, 3})
	accountID := scheduler.AccountID("Account1")
	s.AddAccount(ctx, accountID, accountConfig, nil)

	// Update time, causing quota accounts to accumulate quota.
	s.UpdateTime(ctx, time.Now())

	// Create a task request, and add it to the scheduler queue.
	requestID := scheduler.RequestID("Request1")
	request := scheduler.NewTaskRequest(requestID, accountID, stringset.NewFromSlice("Label1"), nil, time.Now())
	s.AddRequest(ctx, request, time.Now(), scheduler.NullMetricsSink)

	// Inform the scheduler of the existence of an idle worker.
	workerID := scheduler.WorkerID("Worker1")
	s.MarkIdle(ctx, workerID, stringset.NewFromSlice("Label2"), time.Now(), scheduler.NullMetricsSink)

	// False.
	IsOn(requestID, workerID, s)

	// Run a round of the scheduling algorithm, after updating time and accounts
	// again.
	t := time.Now()
	s.UpdateTime(ctx, t)
	// This will return a match between Request1 and Worker1.
	assignments := s.RunOnce(ctx, scheduler.NullMetricsSink)

	// True.
	IsOn(requestID, workerID, s)

	// Your code for handling these assignments goes here...
	HandleAssignments(assignments)

	// Update time, causing quota accounts to be charged for their running tasks
	// In this case, Account1 will be charged for Request1 running on Worker1.
	s.UpdateTime(ctx, time.Now())

	// Notify the scheduler that the task has started running on that worker.
	// This is an acknowledgement of the above assignment.
	// Note: the account is already being charged for this task prior to the
	// notification. The notification ensures consistency of request and worker
	// state, but does not affect account state.
	s.NotifyTaskRunning(ctx, "Request1", "Worker1", time.Now(), scheduler.NullMetricsSink)

	// True.
	IsOn(requestID, workerID, s)

	// Update time, causing quota accounts to again accumulate quota or be charged
	// quota for their running tasks.
	s.UpdateTime(ctx, time.Now())

	// Notifications that contradict the scheduler's state estimate will cause
	// inconsistent records to be deleted from the state.

	// Notify the scheduler that a different task is now running on Worker1,
	// causing records about that worker and previous request to be deleted.
	// Note that this deletion will not affect the current balance of Account1;
	// quota that was spent already on Request1 will not be refunded.
	s.NotifyTaskRunning(ctx, "Request2", "Worker1", time.Now(), scheduler.NullMetricsSink)

	// False.
	IsOn(requestID, workerID, s)

	// Output:
	// Request1 is on Worker1? false
	// Request1 is on Worker1? true
	// Request1 is on Worker1? true
	// Request1 is on Worker1? false
}
