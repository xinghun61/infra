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
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
)

const (
	// Do not ask gerrit about a change more than once every hour.
	pollInterval = time.Hour
	// Fail the audit if the reviewer does not +1 the commit within 7 days.
	gracePeriod = time.Hour * 24 * 7
	// Post the reminder about the TBR deadline only after 1 day.
	reminderDelay = time.Hour * 24
)

// TBRWhiteList is the list of accounts that can create TBR commits that do not need
// to be audited.
var TBRWhiteList = stringset.NewFromSlice(
	"recipe-mega-autoroller@chops-service-accounts.iam.gserviceaccount.com",
	"chromium-autoroll@skia-public.iam.gserviceaccount.com",
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
// owner has reviewed the change.
type ChangeReviewed struct{}

// GetName returns the name of the rule.
func (rule ChangeReviewed) GetName() string {
	return "ChangeReviewed"
}

// shouldSkip decides if a given commit shouldn't be audited with this rule.
//
// E.g. if it's authored by an authorized automated account.
func (rule ChangeReviewed) shouldSkip(rc *RelevantCommit) bool {
	return TBRWhiteList.Has(rc.AuthorAccount)
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
	} else if prevResult != nil {
		// Preserve any metadata from the previous execution of the rule.
		result.MetaData = prevResult.MetaData
	}
	if rule.shouldSkip(rc) {
		result.RuleResultStatus = ruleSkipped
		return result
	}
	rc.LastExternalPoll = time.Now()
	change := getChangeWithLabelDetails(ctx, ap, rc, cs)
	owner := change.Owner.AccountID
	crLabelInfo, exists := change.Labels["Code-Review"]
	if !exists {
		panic(fmt.Sprintf("The gerrit change for Commit %v does not have the 'Code-Review' label.", rc.CommitHash))
	}
	maxValue, err := getMaxLabelValue(crLabelInfo.Values)
	if err != nil {
		// TODO(crbug.com/978167): Stop using panics for this sort of errors.
		panic(err)
	}
	for _, vote := range crLabelInfo.All {
		if int(vote.Value) == maxValue && vote.AccountID != owner {
			// Valid approver found.
			result.RuleResultStatus = rulePassed
			return result
		}
	}
	deadline := rc.CommitTime.Add(gracePeriod)
	if deadline.After(time.Now()) {
		result.RuleResultStatus = rulePending
		// Only post a reminder if `reminderDelay` has elapsed since the commit time.
		if prevResult != nil && time.Now().After(rc.CommitTime.Add(reminderDelay)) {
			// Only post a reminder if it hasn't been done already.
			if _, ok := prevResult.GetToken(ctx, "TBRReminderSent"); !ok {
				result.SetToken(ctx, "TBRReminderSent", "Sent")
				// Notify the CL that it needs to be approved by a valid reviewer
				// within `gracePeriod`.
				if err := postReminder(ctx, change, deadline, cs); err != nil {
					logging.WithError(err).Errorf(
						ctx, "Unable to post reminder on change %v", change.ChangeID)
				}
			}
		}
	} else {

		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf(
			"The commit was not approved by a reviewer other than the owner within %d days of landing.",
			int64(gracePeriod.Hours()/24))
	}
	return result
}

func getChangeWithLabelDetails(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *gerrit.Change {
	cls, _, err := cs.gerrit.ChangeQuery(ctx, gerrit.ChangeQueryParams{
		Query: fmt.Sprintf("commit:%s", rc.CommitHash),
		Options: []string{
			"DETAILED_LABELS",
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

func postReminder(ctx context.Context, change *gerrit.Change, deadline time.Time, cs *Clients) error {
	ri := &gerrit.ReviewInput{
		Message: fmt.Sprintf("This change needs to be reviewed by a valid reviewer by %v", deadline),
	}
	_, err := cs.gerrit.SetReview(ctx, change.ChangeID, "current", ri)
	return err
}
