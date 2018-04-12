// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

// NotificationFunc is a type that needs to be implemented by functions
// intended to notify about violations in rules.
// The notification function is expected to determine if there is a violation
// by checking the results of calling .GetViolations() on the RelevantCommit
// and not just blindly send a notification.
//
// The state parameter is expected to be used to keep the state between retries
// to avoid duplicating notifications, its value will be either the empty string
// or the first element of the return value of a previous call to this function
// for the same commit.
//
// e.g. Return ('notificationSent', nil) if everything goes well, and if the
// incoming state already equals 'notificationSent', then don't send the
// notification, as that would indicate that a previous call already took care
// of that. The state string is a short freeform string that only needs to be
// understood by the NotificationFunc itself, and should exclude colons (`:`).
type NotificationFunc func(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error)

// ViolationNotifier is handler meant to notify about violations to audit
// policies by calling the notification functions registered for each ruleSet
// that matches a commit in the auditCompletedWithViolation status.
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

	cq := ds.NewQuery("RelevantCommit").Ancestor(cfgk).Eq("Status", auditCompletedWithViolation).Eq("NotifiedAll", false)
	ds.Run(ctx, cq, func(rc *RelevantCommit) {
		errors := []error{}
		for ruleSetName, ruleSet := range cfg.Rules {
			if ruleSet.MatchesRelevantCommit(rc) {
				state := rc.GetNotificationState(ruleSetName)
				state, err = ruleSet.NotificationFunction()(ctx, cfg, rc, cs, state)
				if err != nil {
					errors = append(errors, err)
				}
				rc.SetNotificationState(ruleSetName, state)
			}
		}
		if len(errors) == 0 {
			rc.NotifiedAll = true
		}
		for _, e := range errors {
			logging.WithError(e).Errorf(ctx, "Failed notification for detected violation on %s.",
				cfg.LinkToCommit(rc.CommitHash))
			NotificationFailures.Add(ctx, 1, "Violation", repo)
		}

		if err = ds.Put(ctx, rc); err != nil {
			http.Error(resp, err.Error(), 500)
			return
		}
	})

	cq = ds.NewQuery("RelevantCommit").Ancestor(cfgk).Eq("Status", auditFailed).Eq("NotifiedAll", false)
	ds.Run(ctx, cq, func(rc *RelevantCommit) {
		err := reportAuditFailure(ctx, cfg, rc, cs)

		if err == nil {
			rc.NotifiedAll = true
			err = ds.Put(ctx, rc)
			if err != nil {
				logging.WithError(err).Errorf(ctx, "Failed to save notification state for failed audit on %s.",
					cfg.LinkToCommit(rc.CommitHash))
				NotificationFailures.Add(ctx, 1, "AuditFailure", repo)
			}
		} else {
			logging.WithError(err).Errorf(ctx, "Failed to file bug for audit failure on %s.", cfg.LinkToCommit(rc.CommitHash))
			NotificationFailures.Add(ctx, 1, "AuditFailure", repo)
		}
	})
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
	// Route any failure to audit to Findit's team as they own this tool.
	// TODO(crbug.com/798842): Use a custom component for this.
	issueID := int32(0)
	issueID, err = postIssue(ctx, cfg, summary, description, cs, []string{"Tools>Test>Findit>Autorevert"}, []string{"AuditFailure"})
	if err == nil {
		rc.SetNotificationState("AuditFailure", fmt.Sprintf("BUG=%d", issueID))
		// Do not sent further notifications for this commit. This needs
		// to be audited by hand.
		rc.NotifiedAll = true
	}
	return err
}
