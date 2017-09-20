// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"
	"strings"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
	"go.chromium.org/luci/server/router"

	"infra/monorail"
)

var (
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
)

// ViolationNotifier is handler meant to notify about violation to audit
// policies by filing bugs in monorail.
//
// Note that this is called directly by the commit auditor handler instead of
// being an endpoint, as this reduces the latency between the detection of the
// violation and the notification.
func ViolationNotifier(rc *router.Context) {
	ctx, resp := rc.Context, rc.Writer
	cfg, repo, err := loadConfig(rc)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	cs, err := initializeClients(ctx, cfg)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	repoState := &RepoState{RepoURL: cfg.RepoURL()}
	if err := ds.Get(ctx, repoState); err != nil {
		http.Error(resp, fmt.Sprintf("The specified repository %s is not configured", repo), 400)
		return
	}

	cfgk := ds.KeyForObj(ctx, repoState)

	cq := ds.NewQuery("RelevantCommit").Ancestor(cfgk).Eq("Status", auditCompletedWithViolation).Eq("IssueID", 0)
	ds.Run(ctx, cq, func(rc *RelevantCommit) {
		err := reportViolation(ctx, cfg, rc, cs)
		if err != nil {
			logging.WithError(err).Errorf(ctx, "Failed to file bug for detected violation on %s.", cfg.LinkToCommit(rc.CommitHash))
			NotificationFailures.Add(ctx, 1, "Violation", repo)
		}
	})

	cq = ds.NewQuery("RelevantCommit").Ancestor(cfgk).Eq("Status", auditFailed).Eq("IssueID", 0)
	ds.Run(ctx, cq, func(rc *RelevantCommit) {
		err := reportAuditFailure(ctx, cfg, rc, cs)
		if err != nil {
			logging.WithError(err).Errorf(ctx, "Failed to file bug for audit failure on %s.", cfg.LinkToCommit(rc.CommitHash))
			NotificationFailures.Add(ctx, 1, "AuditFailure", repo)
		}
	})
}

// reportViolation checks if the failure has already been reported to monorail
// and files a new bug if it hasn't. If a bug already exists this function will
// try to add a comment and associate it to the bug.
func reportViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients) error {
	summary := fmt.Sprintf("Audit violation detected on %q", rc.CommitHash)
	if rc.IssueID == 0 {
		sa, err := info.ServiceAccount(ctx)
		if err != nil {
			return err
		}

		existingIssue, err := getIssueBySummaryAndAccount(ctx, cfg, summary, sa, cs)
		if err != nil {
			return err
		}

		if existingIssue == nil || !isValidIssue(existingIssue, sa, cfg) {
			rc.IssueID, err = postIssue(ctx, cfg, summary, resultText(cfg, rc, false), cs)
			if err != nil {
				return err
			}

			err = ds.Put(ctx, rc)
			if err != nil {
				return err
			}
		} else {
			// The issue exists and is valid, but it's not
			// associated with the datastore entity for this commit.
			rc.IssueID = existingIssue.Id

			err = postComment(ctx, cfg, existingIssue, resultText(cfg, rc, true), cs)
			if err != nil {
				return err
			}

			err = ds.Put(ctx, rc)
			if err != nil {
				return err
			}

		}
	}
	return nil
}

// reportAuditFailure is meant to file a bug about a revision that has
// repeatedly failed to be audited. i.e. one ore more rules panic on each run.
//
// This does not necessarily mean that a policy has been violated, but only
// that the audit app has not been able to determine whether one exists. One
// such failure could be due to a bug in one of the rules or an error in one of
// the services we depend on (monorail, gitiles, gerrit, milo).
func reportAuditFailure(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients) error {
	summary := fmt.Sprintf("Audit on %q failed over %d times", rc.CommitHash, rc.Retries)
	description := fmt.Sprintf("commit %s has caused the audit process to fail repeatedly, "+
		"please audit by hand and don't close this bug until the root cause of the failure has been "+
		"identified and resolved.", cfg.LinkToCommit(rc.CommitHash))

	var err error
	rc.IssueID, err = postIssue(ctx, cfg, summary, description, cs)
	if err != nil {
		return err
	}

	err = ds.Put(ctx, rc)
	if err != nil {
		return err
	}

	return nil
}

// isValidIssue checks that the monorail issue was created by the app and
// has the correct component and summary. This is to avoid someone suppressing
// an audit alert by creating a spurious bug.
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
		for _, c := range iss.Components {
			if c == cfg.MonorailComponent {
				return true
			}
		}
	}
	return false
}
