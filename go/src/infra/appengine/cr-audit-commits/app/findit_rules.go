// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
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

	// MaxRetriesPerCommit indicates how many times the auditor can retry
	// audting a commit if some rules are panicking. This retry is meant to
	// handle transient errors on the underlying services.
	MaxRetriesPerCommit = 6 // Thirty minutes if checking every 5 minutes.
)

// This is the numeric result code for FAILURE. (As buildbot defines it)
var failedResultCode = 2

var failableStepNames = []string{"compile"}

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
func AutoCommitsPerDay(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AutoCommitsPerDay"
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
func AutoRevertsPerDay(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AutoRevertsPerDay"
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
func CulpritAge(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "CulpritAge"

	_, culprit := getRevertAndCulpritChanges(ctx, ap, rc, cs)
	if culprit == nil {
		panic(fmt.Errorf("Commit %q does not appear to be a revert according to gerrit", rc.CommitHash))
	}

	c, err := cs.gitiles.Log(ctx, ap.RepoCfg.BaseRepoURL, culprit.CurrentRevision, gitiles.Limit(1))
	if err != nil {
		panic(err)
	}
	if len(c) == 0 {
		panic(fmt.Sprintf("commit %s not found in repo.", culprit.CurrentRevision))
	}
	commitTime := c[0].Committer.Time.Time
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
func CulpritInBuild(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "CulpritInBuild"

	_, culprit := getRevertAndCulpritChanges(ctx, ap, rc, cs)
	if culprit == nil {
		panic(fmt.Errorf("Commit %q does not appear to be a revert according to gerrit",
			rc.CommitHash))
	}

	buildURL, failedBuildInfo := getFailedBuild(ctx, cs.milo, rc)

	changeFound := false
	if failedBuildInfo != nil {
		for _, c := range failedBuildInfo.SourceStamp.Changes {
			if c.Revision == culprit.CurrentRevision {
				changeFound = true
				break
			}
		}
	}
	if changeFound {
		result.RuleResultStatus = rulePassed
	} else {
		result.RuleResultStatus = ruleFailed
		if buildURL != "" {
			result.Message = fmt.Sprintf("Hash %s not found in changes for build %q",
				culprit.CurrentRevision, buildURL)
		} else {
			result.Message = fmt.Sprintf(
				"The revert does not point to a failed build, expected link prefixed with \"%s\"",
				failedBuildPrefix)
		}
	}
	return result
}

// TODO(robertocn): Move all gerrit/milo/gitiles/monorail specific logic to a
// file dedicated to each external dependency.

// getRevertAndCulpritChanges gets (through Gerrit) the details of the revert
// CL and  the CL it reverts.
//
// Note: The RevertOf property of a Change does not guarantee that the cl is a
// pure revert of another; instead, the get-pure-revert api of Gerrit needs to
// be checked, like RevertOfCulprit below does.
func getRevertAndCulpritChanges(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) (*gerrit.Change, *gerrit.Change) {
	cls, _, err := cs.gerrit.ChangeQuery(ctx, gerrit.ChangeQueryRequest{Query: rc.CommitHash})
	if err != nil {
		panic(err)
	}
	if len(cls) == 0 {
		panic(fmt.Sprintf("no CL found for commit %q", rc.CommitHash))
	}
	revert, err := cs.gerrit.GetChangeDetails(ctx, cls[0].ChangeID, []string{})

	if err != nil {
		panic(err)
	}
	if revert.RevertOf == 0 {
		return revert, nil
	}

	culprit, err := cs.gerrit.GetChangeDetails(ctx, strconv.Itoa(revert.RevertOf), []string{"CURRENT_REVISION"})
	if err != nil {
		panic(err)
	}
	if culprit.CurrentRevision == "" {
		panic(fmt.Sprintf("Could not get current_revision property for cl %q", culprit.ChangeNumber))
	}
	return revert, culprit
}

// FailedBuildIsCompileFailure is a RuleFunc that verifies that the referred
// build contains a failed compile step.
func FailedBuildIsCompileFailure(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "FailedBuildIsCompileFailure"

	buildURL, failedBuildInfo := getFailedBuild(ctx, cs.milo, rc)

	if failedBuildInfo != nil {

		for _, s := range failedBuildInfo.Steps {
			r, _ := s.Result()
			for _, fs := range failableStepNames {
				if s.Name == fs {
					if int(r) == failedResultCode {
						result.RuleResultStatus = rulePassed
						return result
					}
				}
			}
		}
	}
	result.RuleResultStatus = ruleFailed
	if buildURL != "" {
		result.Message = fmt.Sprintf("Referred build %q does not have an expected failure in either of the following steps: %s",
			buildURL, failableStepNames)
	} else {
		result.Message = fmt.Sprintf(
			"The revert does not point to a failed build, expected link prefixed with \"%s\"",
			failedBuildPrefix)
	}
	return result
}

// RevertOfCulprit is a RuleFunc that verifies that the reverting commit is a
// revert of the named culprit.
func RevertOfCulprit(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "RevertOfCulprit"
	result.RuleResultStatus = ruleFailed

	revert, culprit := getRevertAndCulpritChanges(ctx, ap, rc, cs)
	if culprit == nil {
		result.Message = fmt.Sprintf("Commit %q does not appear to be a revert, according to gerrit",
			rc.CommitHash)
		return result
	}

	pr, err := cs.gerrit.IsChangePureRevert(ctx, revert.ChangeID)
	if err != nil {
		panic(err)
	}
	if !pr {
		result.Message = fmt.Sprintf("Commit %q is a revert but not a *pure* revert, according to gerrit",
			rc.CommitHash)
		return result
	}

	// The CommitMessage of the revert must contain the culprit' hash.
	if !strings.Contains(rc.CommitMessage, culprit.CurrentRevision) {
		result.Message = fmt.Sprintf("Commit %q does not include the revision it reverts in its commit message",
			rc.CommitHash)
		return result
	}
	result.RuleResultStatus = rulePassed
	return result
}

// OnlyCommitsOwnChange is a RuleFunc that verifies that commits landed by the
// service account were also authored by that service account.
func OnlyCommitsOwnChange(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "OnlyCommitsOwnChange"
	result.RuleResultStatus = ruleFailed
	if rc.CommitterAccount == ap.TriggeringAccount {
		if rc.CommitterAccount != rc.AuthorAccount {
			result.RuleResultStatus = ruleFailed
			result.Message = fmt.Sprintf("Service account %s committed a commit by someone else: %s",
				rc.CommitterAccount, rc.AuthorAccount)
			return result
		}
	}
	result.RuleResultStatus = rulePassed
	return result
}
