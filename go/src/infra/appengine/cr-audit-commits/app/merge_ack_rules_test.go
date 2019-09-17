// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	"infra/monorail"
)

func TestMergeAckRules(t *testing.T) {

	Convey("Merge Acknowledgement rules work", t, func() {
		ctx := memory.Use(context.Background())
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:  datastore.KeyForObj(ctx, rs),
			CommitHash:    "b07c0de",
			Status:        auditScheduled,
			CommitMessage: "Acknowledging merges into a release branch",
		}
		cfg := &RepoConfig{
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "3325",
			Metadata:    "MilestoneNumber:65",
		}
		ap := &AuditParams{
			TriggeringAccount: "releasebot@sample.com",
			RepoCfg:           cfg,
		}
		testClients := &Clients{}
		testClients.monorail = mockMonorailClient{
			gi: &monorail.Issue{},
			ii: &monorail.InsertIssueResponse{
				Issue: &monorail.Issue{},
			},
		}
		Convey("Change to commit has a valid bug", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 123456,
				},
			}
			rc.CommitMessage = "This change has a valid bug ID \nBUG:123456"
			// Run rule
			rr := AcknowledgeMerge{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, notificationRequired)
		})
		Convey("Change to commit has no bug", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 123456,
				},
			}
			rc.CommitMessage = "This change has no bug attached"
			// Run rule
			rr := AcknowledgeMerge{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleSkipped)
		})
	})
}
