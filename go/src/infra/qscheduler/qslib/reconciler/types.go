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

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/scheduler"

	"go.chromium.org/luci/common/data/stringset"
)

// State is the state of a reconciler.
type State struct {
	// Internal proto representation of reconciler state.
	proto *protos.Reconciler
}

// TaskWaitingRequest encapsulates the arguments to NotifyTaskWaiting.
type TaskWaitingRequest struct {
	// AccountID for the request.
	AccountID scheduler.AccountID

	// BaseLabels of the request that is waiting.
	BaseLabels stringset.Set

	// Time at which the task was first enqueued.
	EnqueueTime time.Time

	// ProvisionableLabels of the request that is waiting.
	ProvisionableLabels stringset.Set

	// RequestID of the request that is waiting.
	RequestID scheduler.RequestID

	// Tags is the set of tags for the request.
	Tags []string

	// Time at which the task was waiting.
	Time time.Time
}

// TaskRunningRequest encapsulates the arguments to NotifyTaskRunning.
type TaskRunningRequest struct {
	// RequestID of the request that is running.
	RequestID scheduler.RequestID

	// Time at which the task was running.
	Time time.Time

	// WorkerID of the worker that is running the task.
	WorkerID scheduler.WorkerID
}

// TaskAbsentRequest encapsulates the arguments to NotifyTaskAbsent.
type TaskAbsentRequest struct {
	// RequestID of the request that is running.
	RequestID scheduler.RequestID

	// Time at which the task was running.
	Time time.Time

	// WorkerID of the worker that is running the task.
	WorkerID scheduler.WorkerID
}
