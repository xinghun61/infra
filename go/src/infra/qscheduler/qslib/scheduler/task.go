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

	"go.chromium.org/luci/common/data/stringset"
)

// NewTaskRequest creates a new TaskRequest.
func NewTaskRequest(id RequestID, accountID AccountID, provisionableLabels stringset.Set,
	baseLabels stringset.Set, enqueueTime time.Time) *TaskRequest {
	return &TaskRequest{
		AccountID:           accountID,
		BaseLabels:          baseLabels,
		ProvisionableLabels: provisionableLabels,
		EnqueueTime:         enqueueTime,
		examinedTime:        unixZeroTime,
		ID:                  id,
	}
}

// confirm updates a request's confirmed time (to acknowledge that its state
// is consistent with authoritative source as of this time). The update is
// only applied if it is a forward-in-time update or if the existing time
// was undefined.
func (r *TaskRequest) confirm(t time.Time) {
	if r.confirmedTime.Before(t) {
		r.confirmedTime = t
	}
}
