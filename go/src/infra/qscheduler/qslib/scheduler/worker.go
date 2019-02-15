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
	"time"
)

// IsIdle returns whether the given worker is currently idle.
func (w *Worker) IsIdle() bool {
	return w.runningTask == nil
}

// RunningRequest returns the currently running request for this worker.
func (w *Worker) RunningRequest() *TaskRequest {
	if !w.IsIdle() {
		return w.runningTask.request
	}
	return nil
}

// RunningPriority returns the priority of the currently running request.
func (w *Worker) RunningPriority() Priority {
	if !w.IsIdle() {
		return w.runningTask.priority
	}
	return FreeBucket
}

// latestConfirmedTime returns the newer of the its ConfirmedTime or that of the
// request it is running (if it is running one).
func (w *Worker) latestConfirmedTime() time.Time {
	t := w.confirmedTime
	if w.IsIdle() {
		return t
	}
	tr := w.runningTask.request.confirmedTime
	if t.Before(tr) {
		return tr
	}
	return t
}

// confirm updates a worker's confirmed time (to acknowledge that its state
// is consistent with authoritative source as of this time). The update is
// only applied if it is a forward-in-time update.
func (w *Worker) confirm(t time.Time) {
	if w.confirmedTime.Before(t) {
		w.confirmedTime = t
	}
}
