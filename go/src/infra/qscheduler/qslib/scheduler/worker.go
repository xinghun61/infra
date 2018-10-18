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

	"infra/qscheduler/qslib/tutils"
)

// isIdle returns whether the given worker is currently idle.
func (w *Worker) isIdle() bool {
	return w.RunningTask == nil
}

// latestConfirmedTime returns the newer of the its ConfirmedTime or that of the
// request it is running (if it is running one).
func (w *Worker) latestConfirmedTime() time.Time {
	t := tutils.Timestamp(w.ConfirmedTime)
	if w.isIdle() {
		return t
	}
	tr := tutils.Timestamp(w.RunningTask.Request.ConfirmedTime)
	if tr.After(t) {
		return tr
	}
	return t
}

// confirm updates a worker's confirmed time (to acknowledge that its state
// is consistent with authoritative source as of this time). The update is
// only applied if it is a forward-in-time update.
func (w *Worker) confirm(t time.Time) {
	if tutils.Timestamp(w.ConfirmedTime).Before(t) {
		w.ConfirmedTime = tutils.TimestampProto(t)
	}
}

// NewWorker creates a new worker, with given labels.
func NewWorker(labels ...string) *Worker {
	return &Worker{
		Labels: labels,
	}
}
