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
	"fmt"
	"net/url"
	"strings"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes/wrappers"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/monorailv2/api/api_proto"
)

const (
	// OptOutLabel stops Arquebus updating the issue, if added.
	OptOutLabel = "Arquebus-Opt-Out"
)

func issueLink(c context.Context, issue *monorail.Issue) string {
	return fmt.Sprintf(
		"https://%s/p/%s/issues/detail?id=%d",
		config.Get(c).MonorailHostname, issue.ProjectName, issue.LocalId,
	)
}

// searchAndUpdateIssues searches and update issues for the Assigner.
func searchAndUpdateIssues(c context.Context, assigner *model.Assigner, task *model.Task) (int, error) {
	assignee, ccs, err := findAssigneeAndCCs(c, assigner, task)
	if err != nil {
		task.WriteLog(c, "Failed to find assignees and CCs; %s", err)
		return 0, err
	}
	if assignee == nil && ccs == nil {
		// early stop if there is no one available to assign or cc issues to.
		task.WriteLog(
			c, "No one was available to be assigned or CCed; "+
				"skipping issue searches and updates",
		)
		return 0, nil
	}

	mc := getMonorailClient(c)
	issues, err := searchIssues(c, mc, assigner, task)
	if err != nil {
		task.WriteLog(c, "Failed to search issues; %s", err)
		return 0, err
	}
	return updateIssues(c, mc, assigner, task, issues, assignee, ccs)
}

func searchIssues(c context.Context, mc monorail.IssuesClient, assigner *model.Assigner, task *model.Task) ([]*monorail.Issue, error) {
	task.WriteLog(c, "Started searching issues")
	query := assigner.IssueQuery
	res, err := mc.ListIssues(c, &monorail.ListIssuesRequest{
		Query:        fmt.Sprintf("%s -label:%s", query.Q, OptOutLabel),
		CannedQuery:  uint32(monorail.SearchScope_OPEN),
		ProjectNames: query.ProjectNames,

		// This assumes that the search query includes a filter to exclude
		// the previously updated issues.
		// TODO(crbug/965385) - provide a solution to write search queries
		// easier and safer.
		Pagination: &monorail.Pagination{
			Start:    0,
			MaxItems: 20,
		},
	})
	if err != nil {
		return nil, err
	}
	if len(res.Issues) == 0 {
	}

	task.WriteLog(c, "Found %d issues", len(res.Issues))
	return res.Issues, nil
}

func updateIssues(c context.Context, mc monorail.IssuesClient, assigner *model.Assigner, task *model.Task, issues []*monorail.Issue, assignee *monorail.UserRef, ccs []*monorail.UserRef) (int, error) {
	nUpdated := 0

	for _, issue := range issues {
		delta, actionable := createIssueDelta(c, task, issue, assignee, ccs)
		if !actionable {
			// no delta found - skip updating the issue.
			continue
		}

		task.WriteLog(c, "Updating %s", issueLink(c, issue))
		if assigner.IsDryRun {
			task.WriteLog(
				c, "Dry-run is set; skip updating %s", issueLink(c, issue),
			)
			continue
		}
		// TODO(crbug/monorail/5629) - If Monorail supports test-and-update API
		// for issues, then use the API instead.
		_, err := mc.UpdateIssue(c, &monorail.UpdateIssueRequest{
			IssueRef: &monorail.IssueRef{
				ProjectName: issue.ProjectName,
				LocalId:     issue.LocalId,
			},
			SendEmail:      true,
			Delta:          delta,
			CommentContent: genCommentContent(c, assigner, task),
		})

		if err != nil {
			logging.Errorf(c, "failed to update the issue: %s", err)
			task.WriteLog(c, "Failed to update the issue: %s", err)
		} else {
			nUpdated++
		}
	}
	task.WriteLog(c, "%d issues updated", nUpdated)
	return nUpdated, nil
}

func createIssueDelta(c context.Context, task *model.Task, issue *monorail.Issue, assignee *monorail.UserRef, ccs []*monorail.UserRef) (delta *monorail.IssueDelta, actionable bool) {
	// Note that Arquebus never unassigns issues from the current owner.
	delta = &monorail.IssueDelta{
		Status:    &wrappers.StringValue{Value: "Assigned"},
		CcRefsAdd: findCcsToAdd(task, issue.CcRefs, ccs),
	}
	if assignee != nil && !proto.Equal(issue.OwnerRef, assignee) {
		actionable = true
		delta.OwnerRef = assignee
		task.WriteLog(c, "Found a new issue owner %s", assignee.DisplayName)
	}
	if len(delta.CcRefsAdd) > 0 {
		actionable = true
		task.WriteLog(c, "Found %s to add in CC", delta.CcRefsAdd)
	}
	return
}

// findCcsToAdd() returns a list of UserRefs that have not been cc-ed yet, but
// should be.
func findCcsToAdd(task *model.Task, existingCCs, proposedCCs []*monorail.UserRef) []*monorail.UserRef {
	if len(proposedCCs) == 0 {
		return []*monorail.UserRef{}
	}
	ccmap := make(map[uint64]*monorail.UserRef, len(existingCCs))
	for _, cc := range existingCCs {
		ccmap[cc.UserId] = cc
	}

	var ccsToAdd []*monorail.UserRef
	for _, cc := range proposedCCs {
		if _, exist := ccmap[cc.UserId]; !exist {
			ccsToAdd = append(ccsToAdd, cc)
		}
	}
	return ccsToAdd
}

func genCommentContent(c context.Context, assigner *model.Assigner, task *model.Task) string {
	taskURL := fmt.Sprintf(
		"https://%s.appspot.com/assigner/%s/task/%d",
		info.AppID(c), url.QueryEscape(assigner.ID), task.ID,
	)
	messages := []string{
		"Issue update by Arquebus.",
		"Task details: " + taskURL,
		fmt.Sprintf(
			"To stop Arquebus updating this issue, please add the label %q.",
			OptOutLabel,
		),
	}
	if assigner.Comment != "" {
		messages = append(
			messages, "-----------------------------------------------",
		)
		messages = append(messages, assigner.Comment)
	}
	return strings.Join(messages, "\n")
}
