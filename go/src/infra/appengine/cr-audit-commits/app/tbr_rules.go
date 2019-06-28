// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gerrit"
)

const (
	// Do not ask gerrit about a change more than once every hour.
	pollInterval = time.Hour
	// Fail the audit if the reviewer does not +1 the commit within 7 days.
	gracePeriod = time.Hour * 24 * 7
)

// getMaxLabelValue determines the highest possible value of a vote for a given
// label. Gerrit represents the values as "-2", "-1", " 0", "+1", "+2" in the
// mapping of values to descriptions, yet the ApprovalInfo has it as an integer,
// hence the conversion.
func getMaxLabelValue(values map[string]string) (int, error) {
	maxIntVal := 0
	unset := true
	for k := range values {
		intVal, err := strconv.Atoi(strings.TrimSpace(k))
		if err != nil {
			return 0, err
		}
		if intVal > maxIntVal || unset {
			unset = false
			maxIntVal = intVal
		}
	}
	if unset {
		return 0, fmt.Errorf("Expected at least one numerical value in the keys of %v", values)
	}
	return maxIntVal, nil

}

// ChangeReviewed is a RuleFunc that verifies that someone other than the
// uploader has reviewed the change.
type ChangeReviewed struct{}

// GetName returns the name of the rule.
func (rule ChangeReviewed) GetName() string {
	return "ChangeReviewed"
}

// Run executes the rule.
func (rule ChangeReviewed) Run(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = rule.GetName()
	prevResult := PreviousResult(ctx, rc, result.RuleName)
	if prevResult != nil && (prevResult.RuleResultStatus != rulePending ||
		// If we checked gerrit recently, wait before checking again, leave the rule as pending.
		rc.LastExternalPoll.After(time.Now().Add(-pollInterval))) {
		return prevResult
	}
	rc.LastExternalPoll = time.Now()
	change := getChangeWithLabelDetailsAndCurrentRevision(ctx, ap, rc, cs)
	uploader := change.Revisions[change.CurrentRevision].Uploader.AccountID
	crLabelInfo, exists := change.Labels["Code-Review"]
	if !exists {
		panic(fmt.Sprintf("The gerrit change for Commit %v does not have the 'Code-Review' label.", rc.CommitHash))
	}
	maxValue, err := getMaxLabelValue(crLabelInfo.Values)
	if err != nil {
		//TODO(crbug.com/978167): Stop using panics for this sort of errors.
		panic(err)
	}
	for _, vote := range crLabelInfo.All {
		if int(vote.Value) == maxValue && vote.AccountID != uploader {
			// Valid approver found.
			result.RuleResultStatus = rulePassed
			return result
		}
	}
	deadline := rc.CommitTime.Add(gracePeriod)
	if deadline.After(time.Now()) {
		result.RuleResultStatus = rulePending
	} else {

		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf(
			"The commit was not approved by a reviewer other than the uploader within %d days of landing.",
			int64(gracePeriod.Hours()/24))
	}
	return result
}

func getChangeWithLabelDetailsAndCurrentRevision(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *gerrit.Change {
	cls, _, err := cs.gerrit.ChangeQuery(ctx, gerrit.ChangeQueryParams{
		Query: fmt.Sprintf("commit:%s", rc.CommitHash),
		Options: []string{
			"DETAILED_LABELS",
			"CURRENT_REVISION",
		},
	})
	if err != nil {
		panic(err)
	}
	if len(cls) == 0 {
		panic(fmt.Sprintf("no CL found for commit %q", rc.CommitHash))
	}
	return cls[0]
}
