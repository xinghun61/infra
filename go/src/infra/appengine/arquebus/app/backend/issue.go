// Copyright 2019 The LUCI Authors.
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

package backend

import (
	"context"

	"go.chromium.org/luci/common/clock"

	"infra/appengine/arquebus/app/backend/model"
)

// searchAndUpdateIssues searches and update issues for the Assigner.
func searchAndUpdateIssues(c context.Context, assigner *model.Assigner, task *model.Task) error {
	defer func() { task.Ended = clock.Now(c).UTC() }()
	assignees, ccs, err := findAssigneeAndCCs(c, assigner)
	if err != nil {
		task.Status = model.TaskStatus_Failed
		return err
	}
	if assignees == nil && ccs == nil {
		// early stop if there is no one available to assign or cc issues to.
		task.WriteLog(c, "No assignee was available.")
		task.WasNoopSuccess = true
	}

	task.Status = model.TaskStatus_Succeeded
	return nil
}
