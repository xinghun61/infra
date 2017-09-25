// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"time"

	ds "go.chromium.org/gae/service/datastore"
)

// AuditStatus is the enum for RelevantCommit.Status.
type AuditStatus int

const (
	auditScheduled AuditStatus = iota
	auditCompleted
	auditCompletedWithViolation
	auditFailed
)

// ToString returns a human-readable version of this status.
func (as AuditStatus) ToString() string {
	switch as {
	case auditScheduled:
		return "Audit Scheduled"
	case auditCompleted:
		return "Audited OK"
	case auditCompletedWithViolation:
		return "Violation Found"
	case auditFailed:
		return "Audit Failed"
	default:
		return fmt.Sprintf("Unknown status: %d", int(as))
	}
}

// ColorCode returns a stirng used to color code the string, as a css class for
// example.
func (as AuditStatus) ColorCode() string {
	switch as {
	case auditCompleted:
		return "green-status"
	case auditCompletedWithViolation:
		return "red-status"
	case auditFailed:
		return "red-status"
	default:
		return "normal-status"
	}
}

// ToShortString returns a short string version of this status meant to be used
// as datapoint labels for metrics.
func (as AuditStatus) ToShortString() string {
	switch as {
	case auditCompleted:
		return "passed"
	case auditCompletedWithViolation:
		return "violation"
	case auditFailed:
		return "failed"
	default:
		return fmt.Sprintf("unknown:%d", int(as))
	}
}

// RuleStatus is the enum for RuleResult.RuleResultStatus.
type RuleStatus int

const (
	ruleFailed RuleStatus = iota
	rulePassed
	ruleSkipped
)

// ToString returns a human-readable version of this status.
func (rs RuleStatus) ToString() string {
	switch rs {
	case ruleFailed:
		return "Rule Failed"
	case rulePassed:
		return "Rule Passed"
	case ruleSkipped:
		return "Rule Skipped"
	default:
		return fmt.Sprintf("Unknown status: %d", int(rs))
	}
}

// ColorCode returns a stirng used to color code the string, as a css class for
// example.
func (rs RuleStatus) ColorCode() string {
	switch rs {
	case ruleFailed:
		return "red-status"
	case rulePassed:
		return "green-status"
	default:
		return "normal-status"
	}
}

// RepoState contains the state for each repository we audit.
type RepoState struct {
	// RepoURL is expected to point to a branch e.g.
	// https://chromium.googlesource.com/chromium/src.git/+/master
	RepoURL string `gae:"$id"`

	LastKnownCommit        string
	LastKnownCommitTime    time.Time
	LastRelevantCommit     string
	LastRelevantCommitTime time.Time
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
	CommitMessage          string `gae:",noindex"`
	IssueID                int32
	Retries                int32
}

// RuleResult represents the result of applying a single rule to a commit.
type RuleResult struct {
	RuleName         string
	RuleResultStatus RuleStatus
	Message          string
}
