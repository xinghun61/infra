// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"strconv"
	"strings"

	"golang.org/x/net/context"
)

const (
	chromeReleaseBotAcc = "chrome-release-bot@chromium.org"
	mergeApprovedLabel  = "Merge-Approved-%s"
)

var chromeTPMs = []string{"cmasso@chromium.org", "govind@chromium.org", "amineer@chromium.org", "abdulsyed@chromium.org",
	"bhthompson@chromium.org", "josafat@chromium.org", "gkihumba@chromium.org", "kbleicher@chromium.org",
	"mmoss@chromium.org", "benmason@chromium.org"}

// OnlyMergeApprovedChange is a RuleFunc that verifies that only approved changes are merged into a release branch.
func OnlyMergeApprovedChange(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "OnlyMergeApprovedChange"
	result.RuleResultStatus = ruleFailed

	// Exclude Chrome release bot changes
	if rc.AuthorAccount == chromeReleaseBotAcc {
		result.RuleResultStatus = rulePassed
		return result
	}

	// Exclude Chrome TPM changes
	for _, tpm := range chromeTPMs {
		if rc.AuthorAccount == tpm {
			result.RuleResultStatus = rulePassed
			return result
		}
	}
	bugID, err := bugIDFromCommitMessage(rc.CommitMessage)

	if err != nil {
		result.Message = fmt.Sprintf("Revision %s was merged to %s release branch with no bug attached!"+
			"\nPlease explain why this change was merged to the branch!", rc.CommitHash, ap.RepoCfg.BranchName)
		return result
	}
	bugList := strings.Split(bugID, ",")
	milestone := ""
	success := false
	for _, bug := range bugList {
		bugNumber, err := strconv.Atoi(bug)
		if err != nil {
			continue
		}
		milestone, success = GetToken(ctx, "MilestoneNumber", ap.RepoCfg.Metadata)
		if !success {
			panic("MilestoneNumber not specified in repository configuration")
		}
		mergeLabel := fmt.Sprintf(mergeApprovedLabel, milestone)
		vIssue, err := issueFromID(ctx, ap.RepoCfg, int32(bugNumber), cs)
		if err != nil {
			result.Message = fmt.Sprintf("Revision %s was merged to %s release branch with an invalid bug attached!"+
				"\nPlease explain why this change was merged to the branch!", rc.CommitHash, ap.RepoCfg.BranchName)
			return result
		}
		// Check if the issue has a merge approval label
		for _, label := range vIssue.Labels {
			if label == mergeLabel {
				result.RuleResultStatus = rulePassed
				return result
			}
		}
		// Check if the issue has a merge approval label in the comment history
		comments, _ := listCommentsFromIssueID(ctx, ap.RepoCfg, int32(bugNumber), cs)
		for _, comment := range comments {
			if strings.Contains(comment.Content, mergeLabel) {
				result.RuleResultStatus = rulePassed
				return result
			}
		}
	}
	result.Message = fmt.Sprintf("Revision %s was merged to %s branch with no merge approval from "+
		"a TPM! \nPlease explain why this change was merged to the branch!", rc.CommitHash, ap.RepoCfg.BranchName)
	return result
}
