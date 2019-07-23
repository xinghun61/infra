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
	"errors"
	"fmt"
	"net/url"
	"strings"
	"sync/atomic"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes/wrappers"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/monorailv2/api/api_proto"
)

const (
	// OptOutLabel stops Arquebus updating the issue, if added.
	OptOutLabel = "Arquebus-Opt-Out"
	// IssueUpdateMaxConcurrency is the maximum number of
	// monorail.UpdateIssue()s that can be invoked in parallel.
	IssueUpdateMaxConcurrency = 4
)

// searchAndUpdateIssues searches and update issues for the Assigner.
func searchAndUpdateIssues(c context.Context, assigner *model.Assigner, task *model.Task) (int32, error) {
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

	// As long as it succeeded to update at least one issue, the task is
	// not marked as failed.
	nUpdated, nFailed := updateIssues(c, mc, assigner, task, issues, assignee, ccs)
	if nUpdated == 0 && nFailed > 0 {
		return 0, errors.New("all issue updates failed")
	}
	return nUpdated, nil
}

func searchIssues(c context.Context, mc monorail.IssuesClient, assigner *model.Assigner, task *model.Task) ([]*monorail.Issue, error) {
	task.WriteLog(c, "Started searching issues")

	// Inject -label:Arquebus-Opt-Out into the search query.
	var query strings.Builder
	s := strings.Split(assigner.IssueQuery.Q, " OR ")
	for i, q := range s {
		// Split("ABC OR ", " OR ") returns ["ABC", ""]
		if q == "" {
			continue
		}
		query.WriteString(fmt.Sprintf("%s -label:%s", q, OptOutLabel))
		if i < (len(s) - 1) {
			query.WriteString(" OR ")
		}
	}

	res, err := mc.ListIssues(c, &monorail.ListIssuesRequest{
		Query:        query.String(),
		CannedQuery:  uint32(monorail.SearchScope_OPEN),
		ProjectNames: assigner.IssueQuery.ProjectNames,

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

	task.WriteLog(c, "Found %d issues", len(res.Issues))
	return res.Issues, nil
}

// updateIssues update the issues with the desired status and property values.
//
// It is expected that Monorail may become flaky, unavailable, or slow
// temporarily. Therefore, updateIssues tries to update as many issues as
// possible.
func updateIssues(c context.Context, mc monorail.IssuesClient, assigner *model.Assigner, task *model.Task, issues []*monorail.Issue, assignee *monorail.UserRef, ccs []*monorail.UserRef) (nUpdated, nFailed int32) {
	update := func(issue *monorail.Issue) {
		delta, err := createIssueDelta(c, mc, task, issue, assignee, ccs)
		switch {
		case err != nil:
			atomic.AddInt32(&nFailed, 1)
			return
		case delta == nil:
			writeTaskLogWithLink(
				c, task, issue, "No delta found; skip updating",
			)
			return
		}
		if assigner.IsDryRun {
			// dry-run is checked here, because it is expected to run all
			// the steps, but UpdateIssue.
			writeTaskLogWithLink(
				c, task, issue, "Dry-run is set; skip updating",
			)
			return
		}
		writeTaskLogWithLink(c, task, issue, "Updating")
		_, err = mc.UpdateIssue(c, &monorail.UpdateIssueRequest{
			IssueRef: &monorail.IssueRef{
				ProjectName: issue.ProjectName,
				LocalId:     issue.LocalId,
			},
			SendEmail:      true,
			Delta:          delta,
			CommentContent: genCommentContent(c, assigner, task),
		})
		if err != nil {
			writeTaskLogWithLink(c, task, issue, "UpdateIssue failed: %s", err)
			atomic.AddInt32(&nFailed, 1)
			return
		}
		atomic.AddInt32(&nUpdated, 1)
		return
	}

	parallel.WorkPool(IssueUpdateMaxConcurrency, func(tasks chan<- func() error) {
		for _, issue := range issues {
			// In-Scope variable for goroutine closure.
			issue := issue
			tasks <- func() error {
				update(issue)
				return nil
			}
		}
	})
	return
}

// writeTaskLogWithLink invokes task.WriteLog with a link to the issue.
//
// It's necessary to have a link of the issue added to each log, because
// multiple issue updates are performed in parallel, and it will be hard to
// group logs by the issue, if there is no issue information in each log.
func writeTaskLogWithLink(c context.Context, task *model.Task, issue *monorail.Issue, format string, args ...interface{}) {
	format = fmt.Sprintf(
		"[https://%s/p/%s/issues/detail?id=%d] %s",
		config.Get(c).MonorailHostname, issue.ProjectName, issue.LocalId,
		format,
	)
	task.WriteLog(c, format, args...)
}

func createIssueDelta(c context.Context, mc monorail.IssuesClient, task *model.Task, issue *monorail.Issue, assignee *monorail.UserRef, ccs []*monorail.UserRef) (*monorail.IssueDelta, error) {
	// Monorail search responses often contain several minutes old snapshot
	// of Issue property values. Therefore, it is necessary to invoke
	// GetIssues() to get the fresh data before generating IssueDelta.
	//
	// TODO(crbug/monorail/5629) - If Monorail supports test-and-update API,
	// then use the API instead of GetIssue() + UpdateIssue()
	res, err := mc.GetIssue(c, &monorail.GetIssueRequest{
		IssueRef: &monorail.IssueRef{
			ProjectName: issue.ProjectName,
			LocalId:     issue.LocalId,
		},
	})
	if err != nil {
		// NotFound shouldn't be considered as an error. It is just that
		// the search response contained stale data.
		if status.Code(err) == codes.NotFound {
			writeTaskLogWithLink(c, task, issue, "The issue no longer exists")
			return nil, nil
		}
		writeTaskLogWithLink(c, task, issue, "GetIssue failed: %s", err)
		logging.Errorf(c, "GetIssue failed: %s", err)
		return nil, err
	}
	if issue = res.GetIssue(); issue == nil {
		// If a response doesn't contain a valid Issue object, then it's
		// likely a bug of Monorail.
		writeTaskLogWithLink(c, task, issue, "Invalid response from GetIssue")
		return nil, errors.New("invalid response from GetIssue")
	}

	delta := &monorail.IssueDelta{
		// Arquebus never unassigns issues from the current owner.
		Status:    &wrappers.StringValue{Value: "Assigned"},
		CcRefsAdd: findCcsToAdd(task, issue.CcRefs, ccs),
	}
	needUpdate := false
	if assignee != nil && !proto.Equal(issue.OwnerRef, assignee) {
		needUpdate = true
		delta.OwnerRef = assignee
		writeTaskLogWithLink(
			c, task, issue, "Found a new owner: %s", assignee.DisplayName,
		)
	}
	if len(delta.CcRefsAdd) > 0 {
		needUpdate = true
		writeTaskLogWithLink(
			c, task, issue, "Found new CC(s): %s", delta.CcRefsAdd,
		)
	}
	if needUpdate {
		return delta, nil
	}
	return nil, nil
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
