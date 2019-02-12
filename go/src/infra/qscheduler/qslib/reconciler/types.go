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

	"go.chromium.org/luci/common/data/stringset"
)

// TaskWaitingRequest encapsulates the arguments to NotifyTaskWaiting.
type TaskWaitingRequest struct {
	// Time at which the task was waiting.
	Time time.Time

	// Time at which the task was first enqueued.
	EnqueueTime time.Time

	// RequestID of the request that is waiting.
	RequestID RequestID

	// ProvisionableLabels of the request that is waiting.
	ProvisionableLabels stringset.Set

	// BaseLabels of the request that is waiting.
	BaseLabels stringset.Set

	// AccountID for the request.
	AccountID AccountID
}

// TaskRunningRequest encapsulates the arguments to NotifyTaskRunning.
type TaskRunningRequest struct {
	// Time at which the task was running.
	Time time.Time

	// RequestID of the request that is running.
	RequestID RequestID

	// WorkerID of the worker that is running the task.
	WorkerID WorkerID
}

// TaskAbsentRequest encapsulates the arguments to NotifyTaskAbsent.
type TaskAbsentRequest struct {
	// Time at which the task was running.
	Time time.Time

	// RequestID of the request that is running.
	RequestID RequestID

	// WorkerID of the worker that is running the task.
	WorkerID WorkerID
}
