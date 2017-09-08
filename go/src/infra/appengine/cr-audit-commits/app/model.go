// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"time"

	ds "go.chromium.org/gae/service/datastore"
)

// AuditStatus is the enum for RelevantCommit.Status.
type AuditStatus int

const (
	auditScheduled AuditStatus = iota
	auditCompleted
	auditCompletedWithViolation
)

// RuleStatus is the enum for RuleResult.RuleResultStatus.
type RuleStatus int

const (
	ruleFailed RuleStatus = iota
	rulePassed
	ruleSkipped
)

// RepoState contains the state for each repository we audit.
type RepoState struct {
	// RepoURL is expected to point to a branch e.g.
	// https://chromium.googlesource.com/chromium/src.git/+/master
	RepoURL string `gae:"$id"`

	LastKnownCommit    string
	LastRelevantCommit string
}

// RelevantCommit points to a node in a linked list of commits that have
// been considered relevant by CommitScanner.
type RelevantCommit struct {
	RepoStateKey *ds.Key `gae:"$parent"`
	CommitHash   string  `gae:"$id"`

	PreviousRelevantCommit string
	Status                 AuditStatus
	Result                 []RuleResult
	CommitTime             time.Time
	CommitterAccount       string
	AuthorAccount          string
	CommitMessage          string
}

// RuleResult represents the result of applying a single rule to a commit.
type RuleResult struct {
	RuleName         string
	RuleResultStatus RuleStatus
	Message          string
}
