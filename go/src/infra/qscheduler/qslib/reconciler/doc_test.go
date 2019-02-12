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

package reconciler_test

import (
	"context"
	"fmt"
	"time"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

// WorkerID is a type alias for WorkerID
type WorkerID = scheduler.WorkerID

// RequestID is a type alias for RequestID
type RequestID = scheduler.RequestID

// AccountID is a type alias for AccountID
type AccountID = scheduler.AccountID

func Example() {
	ctx := context.Background()

	// Create a scheduler and reconciler.
	s := scheduler.New(time.Now())
	r := reconciler.New()

	// TODO(akeshet): Use reconciler API to add accounts or account
	// configs.

	// Notify the reconciler of a newly enqueued task request.
	requestID := RequestID("Request1")
	accountID := AccountID("Account1")
	labels := stringset.NewFromSlice("label1")
	t := time.Now()
	waitRequest := &reconciler.TaskWaitingRequest{
		AccountID:           accountID,
		RequestID:           requestID,
		ProvisionableLabels: labels,
		EnqueueTime:         t,
		Time:                t,
	}
	r.NotifyTaskWaiting(ctx, s, scheduler.NullMetricsSink, waitRequest)

	// Notify the reconciler of a new idle worker, and fetch an assignment
	// for it. This will fetch Request1 to run on it.
	workerID := WorkerID("Worker1")
	idleWorker := &reconciler.IdleWorker{ID: workerID, Labels: labels}
	a, _ := r.AssignTasks(ctx, s, time.Now(), scheduler.NullMetricsSink, idleWorker)

	fmt.Printf("%s was assigned %s.\n", a[0].WorkerID, a[0].RequestID)

	// A subsequent call for this worker will return the same task,
	// because the previous assignment has not yet been acknowledged.
	a, _ = r.AssignTasks(ctx, s, time.Now(), scheduler.NullMetricsSink, idleWorker)

	fmt.Printf("%s was again assigned %s.\n", a[0].WorkerID, a[0].RequestID)

	// Acknowledge the that request is running on the worker.
	tp := tutils.TimestampProto(time.Now())
	taskUpdate := &reconciler.TaskInstant{
		State:     reconciler.TaskInstant_RUNNING,
		RequestId: string(requestID),
		WorkerId:  string(workerID),
		Time:      tp,
	}
	r.NotifyTaskRunning(ctx, s, scheduler.NullMetricsSink, taskUpdate)

	// Now, a subsequent AssignTasks call for this worker will return
	// nothing, as there are no other tasks in the queue.
	a, _ = r.AssignTasks(ctx, s, time.Now(), scheduler.NullMetricsSink, idleWorker)
	fmt.Printf("After ACK, there were %d new assignments.\n", len(a))

	// Output:
	// Worker1 was assigned Request1.
	// Worker1 was again assigned Request1.
	// After ACK, there were 0 new assignments.
}
