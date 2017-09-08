// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"strconv"
	"time"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
)

// Role is an enum describing the relationship between an email account and a
// commit. (Such as Committer or Author)
type Role uint8

const (
	// Committer is when the account is present in the committer field of
	// the commit.
	Committer Role = iota

	// Author is when the account is present in the author field of the
	// commit.
	Author
)

const (
	// MaxAutoCommitsPerDay indicates how many commits may be landed by the
	// findit service account in any 24 hour period.
	MaxAutoCommitsPerDay = 4
	// MaxAutoRevertsPerDay indicates how many reverts may be created by the
	// findit service account in any 24 hour period.
	MaxAutoRevertsPerDay = 10

	// MaxCulpritAge indicates the maximum delay allowed between a culprit
	// and findit reverting it.
	MaxCulpritAge = 24 * time.Hour
)

// countRelevantCommits follows the relevant commits previous pointer until a
// commit older than the cutoff time is found, and counts those that match the
// account and action given as parameters.
//
// Panics upon datastore error.
func countRelevantCommits(ctx context.Context, rc *RelevantCommit, cutoff time.Time, account string, role Role) int {
	counter := 0
	current := rc
	for {
		switch {
		case current.CommitTime.Before(cutoff):
			return counter
		case role == Committer:
			if current.CommitterAccount == account {
				counter++
			}
		case role == Author:
			if current.AuthorAccount == account {
				counter++
			}
		}

		if current.PreviousRelevantCommit == "" {
			return counter
		}

		current = &RelevantCommit{
			CommitHash:   current.PreviousRelevantCommit,
			RepoStateKey: rc.RepoStateKey,
		}
		err := ds.Get(ctx, current)
		if err != nil {
			panic(fmt.Sprintf("Could not retrieve relevant commit with hash %s", current.CommitHash))
		}

	}
}

func countCommittedBy(ctx context.Context, rc *RelevantCommit, cutoff time.Time, account string) int {
	return countRelevantCommits(ctx, rc, cutoff, account, Committer)
}

func countAuthoredBy(ctx context.Context, rc *RelevantCommit, cutoff time.Time, account string) int {
	return countRelevantCommits(ctx, rc, cutoff, account, Author)
}

// AutoCommitsPerDay is a RuleFunc that verifies that at most
// MaxAutoCommitsPerDay commits in the 24 hours preceding the triggering commit
// were committed by the triggering account.
func AutoCommitsPerDay(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AutoCommitsPerDay"
	result.RuleResultStatus = ruleFailed
	cutoff := rc.CommitTime.Add(time.Duration(-24) * time.Hour)
	autoCommits := countCommittedBy(ctx, rc, cutoff, ap.TriggeringAccount)
	if autoCommits > MaxAutoCommitsPerDay {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf(
			"%d commits were committed by account %s in 24 hours, and the maximum allowed is %d",
			autoCommits, ap.TriggeringAccount, MaxAutoCommitsPerDay)
	} else {
		result.RuleResultStatus = rulePassed
	}
	return result
}

// AutoRevertsPerDay is a RuleFunc that verifies that at most
// MaxAutoRevertsPerDay commits in the 24 hours preceding the triggering commit
// were authored by the triggering account.
func AutoRevertsPerDay(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AutoRevertsPerDay"
	result.RuleResultStatus = ruleFailed
	cutoff := rc.CommitTime.Add(time.Duration(-24) * time.Hour)
	autoReverts := countAuthoredBy(ctx, rc, cutoff, ap.TriggeringAccount)
	if autoReverts > MaxAutoRevertsPerDay {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf(
			"%d commits were created by %s account in 24 hours, and the maximum allowed is %d",
			autoReverts, ap.TriggeringAccount, MaxAutoRevertsPerDay)
	} else {
		result.RuleResultStatus = rulePassed
	}
	return result
}

// CulpritAge is a RuleFunc that verifies that the culprit being reverted is
// less than 24 hours older than the revert.
func CulpritAge(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "CulpritAge"
	result.RuleResultStatus = ruleFailed

	culprit := getCulpritChange(ctx, ap, rc)

	c, err := ap.RepoCfg.gitilesClient.Log(ctx, ap.RepoCfg.BaseRepoURL, culprit.CurrentRevision, 1)
	if err != nil {
		panic(err)
	}
	if len(c) == 0 {
		panic(fmt.Sprintf("commit %s not found in repo.", culprit.CurrentRevision))
	}
	commitTime, err := c[0].Committer.GetTime()
	if err != nil {
		panic(err)
	}
	if rc.CommitTime.Sub(commitTime) > MaxCulpritAge {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf("The revert %s landed more than %s after the culprit %s landed",
			rc.CommitHash, MaxCulpritAge, c[0].Commit)

	} else {
		result.RuleResultStatus = rulePassed
	}
	return result
}

// CulpritInBuild is a RuleFunc that verifies that the culprit is included in
// the list of changes of the failed build.
func CulpritInBuild(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "CulpritInBuild"
	result.RuleResultStatus = ruleFailed

	buildURL, err := failedBuildFromCommitMessage(rc.CommitMessage)
	if err != nil {
		panic(err)
	}

	culprit := getCulpritChange(ctx, ap, rc)

	failedBuildInfo, err := ap.RepoCfg.miloClient.GetBuildInfo(ctx, buildURL)
	if err != nil {
		panic(err)
	}
	changeFound := false
	for _, c := range failedBuildInfo.SourceStamp.Changes {
		if c.Revision == culprit.CurrentRevision {
			changeFound = true
			break
		}
	}
	if changeFound {
		result.RuleResultStatus = rulePassed
	} else {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf("Hash %s not found in changes for build %q",
			culprit.CurrentRevision, buildURL)
	}
	return result
}

// TODO(robertocn): Move all gerrit/milo/gitiles/monorail specific logic to a
// file dedicated to each external dependency.

// getCulpritChange finds (through Gerrit) the CL being reverted by another.
func getCulpritChange(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *gerrit.Change {
	cls, _, err := ap.RepoCfg.gerritClient.ChangeQuery(ctx, gerrit.ChangeQueryRequest{Query: rc.CommitHash})
	if err != nil {
		panic(err)
	}
	if len(cls) == 0 {
		panic(fmt.Sprintf("no CL found for commit %q", rc.CommitHash))
	}
	d, err := ap.RepoCfg.gerritClient.GetChangeDetails(ctx, cls[0].ChangeID, []string{})

	if err != nil {
		panic(err)
	}
	if d.RevertOf == 0 {
		panic(fmt.Sprintf("Could not get revert_of property for revert %q", rc.CommitHash))
	}
	culprit, err := ap.RepoCfg.gerritClient.GetChangeDetails(ctx, strconv.Itoa(d.RevertOf), []string{"CURRENT_REVISION"})
	if err != nil {
		panic(err)
	}
	if culprit.CurrentRevision == "" {
		panic(fmt.Sprintf("Could not get current_revision property for cl %q", culprit.ChangeNumber))
	}
	return culprit
}
