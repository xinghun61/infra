// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"go.chromium.org/luci/common/tsmon/distribution"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
)

var (
	// ScannedCommits counts commits that have been scanned by this
	// handler.
	ScannedCommits = metric.NewCounter(
		"cr_audit_commits/scanned",
		"Commits that have been scanned by the audit app",
		&types.MetricMetadata{Units: "Commit"},
		field.Bool("relevant"),
		field.String("repo"),
	)

	// AuditedCommits counts commits that have been scanned by this
	// handler.
	//
	// The valid values for the result field are:
	//   - passed: the audit found no problems with the commit,
	//   - violation: the audit found one or more policy violations,
	//   - failed: the audit failed to complete due to errors.
	AuditedCommits = metric.NewCounter(
		"cr_audit_commits/audited",
		"Commits that have been audited by the audit app",
		&types.MetricMetadata{Units: "Commit"},
		field.String("result"),
		field.String("repo"),
	)

	// PerCommitAuditDuration keeps track of how long it takes to run all
	// the rules for a given commit.
	PerCommitAuditDuration = metric.NewCumulativeDistribution(
		"cr_audit_commits/per_commit_audit_duration",
		"Time it takes to apply all rules to a single commit",
		&types.MetricMetadata{Units: types.Milliseconds},
		distribution.DefaultBucketer,
		field.String("result"),
		field.String("repo"),
	)

	// NotificationFailures counts when the app fails to notify about a
	// detected violation or repeated audit failure. Any one of these
	// requires immediate attention.
	NotificationFailures = metric.NewCounter(
		"cr_audit_commits/notification_failure",
		"Audit app failed to file a bug to notify about a detected violation or audit failure",
		&types.MetricMetadata{Units: "Failure"},
		field.String("type"), // Violation or AuditFailure.
		field.String("repo"),
	)

	// RefAuditsDue counts events when audit jobs are to be scheduled for
	// each configured ref.
	RefAuditsDue = metric.NewCounter(
		"cr_audit_commits/ref_audits_due",
		"Audits that are due to be scheduled by the audit app",
		&types.MetricMetadata{Units: "Task"},
		field.Bool("scheduled"), // False if failed to be scheduled.
	)
)
