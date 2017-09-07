// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"time"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
)

// MaxAutoCommitsPerDay indicates how many commits may be landed by the findit
// service account in any 24 hour period.
const MaxAutoCommitsPerDay = 4

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

// countRelevantCommits follows the relevant commits previous pointer until a
// commit older than the cutoff time is found, and counts those that match the
// account and action given as parameters.
//
// Panics upon datastore error.
func countRelevantCommits(ctx context.Context, rc *RelevantCommit, cutoff time.Time, account string, role Role) int {
	counter := 0
	current := rc
	for {
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

	}
}

func countCommittedBy(ctx context.Context, rc *RelevantCommit, cutoff time.Time, account string) int {
	return countRelevantCommits(ctx, rc, cutoff, account, Committer)
}

// AutoCommitsPerDay is a RuleFunc that verifies that at most
// MaxAutoCommitsPerDay commits in the 24 hours preceding the triggering commit
// were committed by the triggering account.
func AutoCommitsPerDay(ctx context.Context, ap *AuditParams, rc *RelevantCommit) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AutoCommitsPerDay"
	result.RuleResultStatus = rulePassed
	cutoff := rc.CommitTime.Add(time.Duration(-24) * time.Hour)
	autoCommits := countCommittedBy(ctx, rc, cutoff, ap.TriggeringAccount)
	if autoCommits > MaxAutoCommitsPerDay {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf(
			"%d commits were committed by account %s in 24 hours, and the maximum allowed is %d",
			autoCommits, ap.TriggeringAccount, MaxAutoCommitsPerDay)
	}
	return result
}
