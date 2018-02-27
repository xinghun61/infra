// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"

	"infra/monorail"
)

func fileBugForFinditViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error) {
	components := []string{"Tools>Test>Findit>Autorevert"}
	labels := []string{"CommitLog-Audit-Violation"}
	return fileBugForViolation(ctx, cfg, rc, cs, state, components, labels)
}

func fileBugForReleaseBotViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error) {
	components := []string{"Infra>Client>Chrome>Release"}
	labels := []string{"CommitLog-Audit-Violation"}
	return fileBugForViolation(ctx, cfg, rc, cs, state, components, labels)
}

func fileBugForMergeApprovalViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error) {
	components := []string{"Infra>Client>Chrome>Release"}
	labels := []string{"CommitLog-Audit-Violation", "Merge-Without-Approval", fmt.Sprintf("M-%d", cfg.MilestoneNumber)}
	return fileBugForViolation(ctx, cfg, rc, cs, state, components, labels)
}

// fileBugForViolation checks if the failure has already been reported to
// monorail and files a new bug if it hasn't. If a bug already exists this
// function will try to add a comment and associate it to the bug.
func fileBugForViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string, components, labels []string) (string, error) {
	summary := fmt.Sprintf("Audit violation detected on %q", rc.CommitHash)
	// Make sure that at least one of the rules that were violated had
	// .FileBug set to true.
	violations := rc.GetViolations()
	fileBug := len(violations) > 0
	labels = append(labels, "Restrict-View-Google")
	if fileBug && state == "" {
		issueID := int32(0)
		sa, err := info.ServiceAccount(ctx)
		if err != nil {
			return "", err
		}

		existingIssue, err := getIssueBySummaryAndAccount(ctx, cfg, summary, sa, cs)
		if err != nil {
			return "", err
		}

		if existingIssue == nil || !isValidIssue(existingIssue, sa, cfg) {
			issueID, err = postIssue(ctx, cfg, summary, resultText(cfg, rc, false), cs, components, labels)
			if err != nil {
				return "", err
			}

		} else {
			// The issue exists and is valid, but it's not
			// associated with the datastore entity for this commit.
			issueID = existingIssue.Id

			err = postComment(ctx, cfg, existingIssue.Id, resultText(cfg, rc, true), cs)
			if err != nil {
				return "", err
			}
		}
		state = fmt.Sprintf("BUG=%d", issueID)
	}
	return state, nil
}

// isValidIssue checks that the monorail issue was created by the app and
// has the correct summary. This is to avoid someone
// suppressing an audit alert by creating a spurious bug.
func isValidIssue(iss *monorail.Issue, sa string, cfg *RepoConfig) bool {
	for _, st := range []string{
		monorail.StatusFixed,
		monorail.StatusVerified,
		monorail.StatusDuplicate,
		monorail.StatusWontFix,
		monorail.StatusArchived,
	} {
		if iss.Status == st {
			// Issue closed, file new one.
			return false
		}
	}
	if strings.HasPrefix(iss.Summary, "Audit violation detected on") && iss.Author.Name == sa {
		return true
	}
	return false
}
