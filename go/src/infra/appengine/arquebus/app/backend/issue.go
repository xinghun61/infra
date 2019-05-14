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

	"infra/appengine/arquebus/app/backend/model"
	"infra/monorailv2/api/api_proto"
)

// searchAndUpdateIssues searches and update issues for the Assigner.
func searchAndUpdateIssues(c context.Context, assigner *model.Assigner, task *model.Task) (int, error) {
	assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
	if err != nil {
		task.WriteLog(c, "Failed to find assignees and ccs; %s", err.Error())
		return 0, err
	}

	if assignee == nil && ccs == nil {
		// early stop if there is no one available to assign or cc issues to.
		task.WriteLog(
			c, "No one was available to be assigned or cc-ed; "+
				"skipping issue searches and updates.",
		)
		return 0, nil
	}

	issues, err := searchIssues(c, assigner, task)
	if err != nil {
		task.WriteLog(c, "Failed to search issues; %s", err.Error())
		return 0, err
	}
	return updateIssues(c, assigner, task, issues, assignee, ccs)
}

func searchIssues(c context.Context, assigner *model.Assigner, task *model.Task) ([]*monorail.Issue, error) {
	// TODO(crbug/849469) implement me
	task.WriteLog(c, "No issues have been found.")
	return nil, nil
}

func updateIssues(c context.Context, assigner *model.Assigner, task *model.Task, issues []*monorail.Issue, assignee *monorail.UserRef, ccs []*monorail.UserRef) (int, error) {
	nUpdated := 0
	for range issues {
		// TODO(crbug/849469) implement me
		nUpdated++
	}
	task.WriteLog(c, "%d issues have been updated.", nUpdated)
	return nUpdated, nil
}
