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

// NewRequest creates a new TaskRequest.
func NewRequest(accountID AccountID, labels []string, enqueueTime time.Time) *TaskRequest {
	return &TaskRequest{
		AccountId:     string(accountID),
		ConfirmedTime: tutils.TimestampProto(enqueueTime),
		EnqueueTime:   tutils.TimestampProto(enqueueTime),
		Labels:        labels,
	}
}

// confirm updates a request's confirmed time (to acknowledge that its state
// is consistent with authoritative source as of this time). The update is
// only applied if it is a forward-in-time update or if the existing time
// was undefined.
func (r *request) confirm(t time.Time) {
	if r.confirmedTime.Before(t) {
		r.confirmedTime = t
	}
}
