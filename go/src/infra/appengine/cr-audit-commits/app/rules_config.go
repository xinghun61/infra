// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/proto/git"
)

// RepoConfig represents the hard-coded config for a monitored repo and a
// pointer to the entity representing its datastore-persisted state.
type RepoConfig struct { // These are expected to be hard-coded.
	BaseRepoURL     string
	GerritURL       string
	BranchName      string
	MilestoneNumber int32
	StartingCommit  string
	MonorailAPIURL  string // Only intended for release branches
	MonorailProject string
	// Do not use "AuditFailure" as a key in this map, it may cause a clash
	// with the notification state for failed audits.
	Rules         map[string]RuleSet
	NotifierEmail string
}

// RepoURL composes the url of the repository by appending the branch.
func (rc *RepoConfig) RepoURL() string {
	return rc.BaseRepoURL + "/+/" + rc.BranchName
}

// LinkToCommit composes a url to a specific commit
func (rc *RepoConfig) LinkToCommit(commit string) string {
	return rc.BaseRepoURL + "/+/" + commit
}

// RuleMap maps each monitored repository to a list of account/rules structs.
var RuleMap = map[string]*RepoConfig{
	"chromium-src-master": {
		BaseRepoURL: "https://chromium.googlesource.com/chromium/src.git",
		GerritURL:   "https://chromium-review.googlesource.com",
		BranchName:  "master",
		// No special meaning, ToT as of the time this line was added.
		StartingCommit:  "bafa682dc0ce1dde367ba44f31f8ec1ad07e569e",
		MonorailAPIURL:  "https://monorail-prod.appspot.com/_ah/api/monorail/v1",
		MonorailProject: "chromium",
		NotifierEmail:   "notifier@cr-audit-commits.appspotmail.com",
		Rules: map[string]RuleSet{
			"findit-rules": AccountRules{
				Account: "findit-for-me@appspot.gserviceaccount.com",
				Funcs: []RuleFunc{
					AutoCommitsPerDay,
					AutoRevertsPerDay,
					CulpritAge,
					CulpritInBuild,
					FailedBuildIsAppropriateFailure,
					RevertOfCulprit,
					OnlyCommitsOwnChange,
				},
				notificationFunction: fileBugForFinditViolation,
			},
			"release-bot-rules": AccountRules{
				Account: "chrome-release-bot@chromium.org",
				Funcs: []RuleFunc{
					OnlyModifiesVersionFile,
				},
				notificationFunction: fileBugForReleaseBotViolation,
			},
		},
	},
	"chromium-src-3325": {
		BaseRepoURL:     "https://chromium.googlesource.com/chromium/src.git",
		GerritURL:       "https://chromium-review.googlesource.com",
		BranchName:      "3325",
		MilestoneNumber: 65,
		StartingCommit:  "1593920eed56dee727e7f78ae5d206052e4ad7e0",
		MonorailAPIURL:  "https://monorail-prod.appspot.com/_ah/api/monorail/v1",
		MonorailProject: "chromium",
		NotifierEmail:   "notifier@cr-audit-commits.appspotmail.com",
		Rules: map[string]RuleSet{
			"merge-approval-rules": AccountRules{
				Account: "*",
				Funcs: []RuleFunc{
					OnlyMergeApprovedChange,
				},
				notificationFunction: fileBugForMergeApprovalViolation,
			},
		},
	},
}

// RuleSet is a group of rules that can be decided to apply or not to a
// specific commit, as a unit.
//
// Note that the methods in this interface are not rules, but tests that can
// decide whether the rules in the set apply to a given commit.
type RuleSet interface {
	MatchesCommit(*git.Commit) bool
	MatchesRelevantCommit(*RelevantCommit) bool
	NotificationFunction() NotificationFunc
}

// AccountRules is a RuleSet that applies to a commit if the commit has a given
// account as either its author or its committer.
type AccountRules struct {
	Account              string
	Funcs                []RuleFunc
	notificationFunction NotificationFunc
}

// NotificationFunction exposes the NotificationFunc assigned to this struct
// as required by the RuleSet interface.
func (ar AccountRules) NotificationFunction() NotificationFunc {
	return ar.notificationFunction
}

// MatchesCommit determines whether the AccountRules set it's bound to, applies
// to the given commit.
func (ar AccountRules) MatchesCommit(c *git.Commit) bool {
	return c.GetCommitter().GetEmail() == ar.Account || c.GetAuthor().GetEmail() == ar.Account
}

// MatchesRelevantCommit determines whether the AccountRules set it's bound to,
// applies to the given commit entity.
func (ar AccountRules) MatchesRelevantCommit(c *RelevantCommit) bool {
	return c.CommitterAccount == ar.Account || c.AuthorAccount == ar.Account
}

// AuditParams exposes object shared by all rules (and the worker goroutines
// they are run on).
type AuditParams struct {
	TriggeringAccount string
	RepoCfg           *RepoConfig
	RepoState         *RepoState
}

// RuleFunc is the function type for audit rules.
//
// They are expected to accept a context, an AuditParams, a Clients struct with
// connections to external services configured and ready, and the datastore
// entity to be audited.
//
// Rules are expected to panic if they cannot determine whether a policy has
// been broken or not.
//
// Rules should return a reference to a RuleResult
type RuleFunc func(context.Context, *AuditParams, *RelevantCommit, *Clients) *RuleResult
