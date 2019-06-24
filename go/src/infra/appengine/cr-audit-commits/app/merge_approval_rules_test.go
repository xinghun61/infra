// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	"infra/monorail"
)

func TestMergeApprovalRules(t *testing.T) {

	Convey("Merge Approval rules work", t, func() {
		ctx := memory.Use(context.Background())
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:  datastore.KeyForObj(ctx, rs),
			CommitHash:    "b07c0de",
			Status:        auditScheduled,
			CommitMessage: "Making sure changes committed are approved",
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
		Convey("Change to commit has a valid bug with merge approval label in comment history", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 123456,
				},
				cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "cmasso@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change has a valid bug ID with merge approval label in comment history \nBUG:123456"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Change to commit has a valid bug prefixed with chromium with merge approval label in comment history", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 123456,
				},
				cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "cmasso@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change has a valid bug ID with merge approval label in comment history \nBug: chromium:123456"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Change to commit has multiple bugs including an invalid one", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 123456,
				},
				cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "cmasso@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change to commit has multiple bugs including an invalid one \nBUG:123456, 654321"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Change to commit has an invalid bug and a valid one with no merge approval label", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id:     123456,
					Labels: []string{},
				},
				cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "cmasso@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{},
							},
						},
					},
				},
			}
			rc.CommitMessage = "Change to commit has an invalid bug and a valid one with no merge approval label \nBug: 265485, 123456"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
		})
		Convey("Change to commit has multiple invalid bugs", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id:     123456,
					Labels: []string{},
				},
				cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{},
				},
			}
			rc.CommitMessage = "All bugs listed on this change to commit are all invalid \nBug: 654321, 587469"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
		})
		Convey("Change to commit is authored by a Chrome TPM", func() {
			rc.CommitMessage = "This change's author is a Chrome TPM"
			rc.AuthorAccount = "cmasso@chromium.org"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Change to commit is committed by a Chrome TPM", func() {
			rc.CommitMessage = "This change's committer is a Chrome TPM"
			rc.CommitterAccount = "cmasso@chromium.org"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Change to commit is by Chrome release bot", func() {
			rc.CommitMessage = "This change's author is Chrome release bot"
			rc.AuthorAccount = "chrome-release-bot@chromium.org"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Change to commit has no bug ID field", func() {
			rc.CommitMessage = "This change does not have a bug ID field"
			rc.CommitHash = "a1b2c3d4e5f6"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			//Check result message
			So(rr.Message, ShouldContainSubstring, rc.CommitHash)

		})
		Convey("Change to commit has an invalid bug ID", func() {
			rc.CommitMessage = "This change has an invalid bug ID \nBug=none"
			rc.CommitHash = "a1b2c3d4e5f6"
			// Run rule
			rr := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			//Check result message
			So(rr.Message, ShouldContainSubstring, rc.CommitHash)
		})

	})
}
