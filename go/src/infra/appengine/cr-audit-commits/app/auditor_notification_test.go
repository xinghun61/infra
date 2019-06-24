// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/mail"
	"go.chromium.org/gae/service/user"

	"infra/monorail"
)

// sendEmailForFinditViolation is not actually used by any RuleSet its purpose
// is to illustrate how one would use sendEmailForViolation to notify about
// violations via email.
func sendEmailForFinditViolation(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error) {
	recipients := []string{"eng-team@dummy.com"}
	subject := "A policy violation was detected on commit %s"
	return sendEmailForViolation(ctx, cfg, rc, cs, state, recipients, subject)
}

func TestNotifier(t *testing.T) {

	Convey("ViolationNotifier handler test", t, func() {
		ctx := memory.UseWithAppID(context.Background(), "cr-audit-commits-test")

		user.GetTestable(ctx).Login("notifier@cr-audit-commits-test.appspotmail.com", "", false)

		testClients := &Clients{}
		Convey("Existing Repo", func() {
			cfg := &RepoConfig{
				BaseRepoURL:     "https://old.googlesource.com/old.git",
				GerritURL:       "https://old-review.googlesource.com",
				BranchName:      "master",
				StartingCommit:  "000000",
				MonorailAPIURL:  "https://monorail-fake.appspot.com/_ah/api/monorail/v1",
				MonorailProject: "fakeproject",
				NotifierEmail:   "notifier@cr-audit-commits-test.appspotmail.com",
				Rules: map[string]RuleSet{"rules": AccountRules{
					Account: "author@test.com",
					Rules: []Rule{
						DummyRule{
							name:   "Dummy rule",
							result: &RuleResult{"Dummy rule", rulePassed, "", "label:Random-Label"},
						},
					},
					notificationFunction: fileBugForFinditViolation,
				}},
			}
			RuleMap["old-repo"] = cfg
			repoState := &RepoState{
				RepoURL:            "https://old.googlesource.com/old.git/+/master",
				LastKnownCommit:    "123456",
				LastRelevantCommit: "999999",
			}
			ds.Put(ctx, repoState)

			Convey("No audits", func() {
				testClients.monorail = mockMonorailClient{
					e: fmt.Errorf("Monorail was called even though there were no failed audits"),
				}
				err := notifyAboutViolations(ctx, cfg, repoState, testClients)
				So(err, ShouldBeNil)
			})
			Convey("No failed audits", func() {
				rsk := ds.KeyForObj(ctx, repoState)
				testClients.monorail = mockMonorailClient{
					e: fmt.Errorf("Monorail was called even though there were no failed audits"),
				}
				rc := &RelevantCommit{
					RepoStateKey:     rsk,
					CommitHash:       "600dc0de",
					Status:           auditCompleted,
					Result:           []RuleResult{{"DummyRule", rulePassed, "", ""}},
					CommitterAccount: "committer@test.com",
					AuthorAccount:    "author@test.com",
					CommitMessage:    "This commit passed all audits.",
				}
				err := ds.Put(ctx, rc)
				So(err, ShouldBeNil)

				err = notifyAboutViolations(ctx, cfg, repoState, testClients)
				So(err, ShouldBeNil)
				rc = &RelevantCommit{
					RepoStateKey: rsk,
					CommitHash:   "600dc0de",
				}
				err = ds.Get(ctx, rc)
				So(err, ShouldBeNil)
				So(rc.GetNotificationState("rules"), ShouldEqual, "")
				So(rc.NotifiedAll, ShouldBeFalse)
			})
			Convey("Failed audits - bug only", func() {
				rsk := ds.KeyForObj(ctx, repoState)
				testClients.monorail = mockMonorailClient{
					il: &monorail.IssuesListResponse{},
					ii: &monorail.InsertIssueResponse{
						Issue: &monorail.Issue{
							Id: 12345,
						},
					},
				}
				rc := &RelevantCommit{
					RepoStateKey:     rsk,
					CommitHash:       "badc0de",
					Status:           auditCompletedWithActionRequired,
					Result:           []RuleResult{{"DummyRule", ruleFailed, "This commit is bad", ""}},
					CommitterAccount: "committer@test.com",
					AuthorAccount:    "author@test.com",
					CommitMessage:    "This commit failed all audits.",
				}
				err := ds.Put(ctx, rc)
				So(err, ShouldBeNil)

				err = notifyAboutViolations(ctx, cfg, repoState, testClients)
				So(err, ShouldBeNil)
				rc = &RelevantCommit{
					RepoStateKey: rsk,
					CommitHash:   "badc0de",
				}
				err = ds.Get(ctx, rc)
				So(err, ShouldBeNil)
				So(rc.GetNotificationState("rules"), ShouldEqual, "BUG=12345")
				So(rc.NotifiedAll, ShouldBeTrue)
				m := mail.GetTestable(ctx)
				So(m.SentMessages(), ShouldBeEmpty)

			})
			Convey("Exceeded retries", func() {
				rsk := ds.KeyForObj(ctx, repoState)
				testClients.monorail = mockMonorailClient{
					ii: &monorail.InsertIssueResponse{
						Issue: &monorail.Issue{
							Id: 12345,
						},
					},
				}
				rc := &RelevantCommit{
					RepoStateKey:     rsk,
					CommitHash:       "b00b00",
					Status:           auditFailed,
					Result:           []RuleResult{},
					CommitterAccount: "committer@test.com",
					AuthorAccount:    "author@test.com",
					CommitMessage:    "This commit panicked and panicked",
					Retries:          MaxRetriesPerCommit + 1,
				}
				err := ds.Put(ctx, rc)
				So(err, ShouldBeNil)

				err = notifyAboutViolations(ctx, cfg, repoState, testClients)
				So(err, ShouldBeNil)
				rc = &RelevantCommit{
					RepoStateKey: rsk,
					CommitHash:   "b00b00",
				}
				err = ds.Get(ctx, rc)
				So(err, ShouldBeNil)
				So(rc.GetNotificationState("AuditFailure"), ShouldEqual, "BUG=12345")
				So(rc.NotifiedAll, ShouldBeTrue)
			})
		})
		Convey("Notification required audits - comment only", func() {
			testClients.monorail = mockMonorailClient{
				gi: &monorail.Issue{
					Id: 8675389,
				},
			}
			cfg := &RepoConfig{
				BaseRepoURL:     "https://old.googlesource.com/old-ack.git",
				GerritURL:       "https://old-review.googlesource.com",
				BranchName:      "master",
				StartingCommit:  "000000",
				MonorailAPIURL:  "https://monorail-fake.appspot.com/_ah/api/monorail/v1",
				MonorailProject: "fakeproject",
				NotifierEmail:   "notifier@cr-audit-commits-test.appspotmail.com",
				Rules: map[string]RuleSet{"rulesAck": AccountRules{
					Account: "author@test.com",
					Rules: []Rule{
						DummyRule{
							name:   "Dummy rule",
							result: &RuleResult{"Dummy rule", notificationRequired, "", "BugNumbers:8675389"},
						},
					},
					notificationFunction: commentOnBugToAcknowledgeMerge,
				}},
				Metadata: "MilestoneNumber:70",
			}
			RuleMap["old-repo-ack"] = cfg
			repoState := &RepoState{
				RepoURL:            "https://old.googlesource.com/old-ack.git/+/master",
				LastKnownCommit:    "123456",
				LastRelevantCommit: "999999",
			}
			ds.Put(ctx, repoState)
			rsk := ds.KeyForObj(ctx, repoState)
			rc := &RelevantCommit{
				RepoStateKey:     rsk,
				CommitHash:       "badc0de",
				Status:           auditCompletedWithActionRequired,
				Result:           []RuleResult{{"DummyRule", notificationRequired, "This commit requires a notification", "BugNumbers:8675389"}},
				CommitterAccount: "committer@test.com",
				AuthorAccount:    "author@test.com",
				CommitMessage:    "This commit requires a notification.",
			}
			err := ds.Put(ctx, rc)
			So(err, ShouldBeNil)

			err = notifyAboutViolations(ctx, cfg, repoState, testClients)
			So(err, ShouldBeNil)

			rc = &RelevantCommit{
				RepoStateKey: rsk,
				CommitHash:   "badc0de",
			}
			err = ds.Get(ctx, rc)
			So(rc.GetNotificationState("rulesAck"), ShouldEqual, "Comment posted on BUG(S)=8675389")
			So(rc.NotifiedAll, ShouldBeTrue)
			m := mail.GetTestable(ctx)
			So(m.SentMessages(), ShouldBeEmpty)
		})
		Convey("Failed audits - email only", func() {
			cfg := &RepoConfig{
				BaseRepoURL:     "https://old.googlesource.com/old-email.git",
				GerritURL:       "https://old-review.googlesource.com",
				BranchName:      "master",
				StartingCommit:  "000000",
				MonorailAPIURL:  "https://monorail-fake.appspot.com/_ah/api/monorail/v1",
				MonorailProject: "fakeproject",
				NotifierEmail:   "notifier@cr-audit-commits-test.appspotmail.com",
				Rules: map[string]RuleSet{"rulesEmail": AccountRules{
					Account: "author@test.com",
					Rules: []Rule{
						DummyRule{
							name:   "Dummy rule",
							result: &RuleResult{"Dummy rule", rulePassed, "", ""},
						},
					},
					notificationFunction: sendEmailForFinditViolation,
				}},
			}
			RuleMap["old-repo-email"] = cfg
			repoState := &RepoState{
				RepoURL:            "https://old.googlesource.com/old-email.git/+/master",
				LastKnownCommit:    "123456",
				LastRelevantCommit: "999999",
			}
			ds.Put(ctx, repoState)
			rsk := ds.KeyForObj(ctx, repoState)
			rc := &RelevantCommit{
				RepoStateKey:     rsk,
				CommitHash:       "badc0de",
				Status:           auditCompletedWithActionRequired,
				Result:           []RuleResult{{"DummyRule", ruleFailed, "This commit is bad", ""}},
				CommitterAccount: "committer@test.com",
				AuthorAccount:    "author@test.com",
				CommitMessage:    "This commit failed all audits.",
			}
			err := ds.Put(ctx, rc)
			So(err, ShouldBeNil)

			err = notifyAboutViolations(ctx, cfg, repoState, testClients)
			So(err, ShouldBeNil)
			rc = &RelevantCommit{
				RepoStateKey: rsk,
				CommitHash:   "badc0de",
			}
			err = ds.Get(ctx, rc)
			So(err, ShouldBeNil)
			m := mail.GetTestable(ctx)
			So(rc.NotifiedAll, ShouldBeTrue)
			So(m.SentMessages()[0], ShouldResemble,
				&mail.TestMessage{
					Message: mail.Message{
						Sender:  "notifier@cr-audit-commits-test.appspotmail.com",
						To:      []string{"eng-team@dummy.com"},
						Subject: "A policy violation was detected on commit badc0de",
						Body:    "Here are the messages from the rules that were broken by this commit:\n\nThis commit is bad",
					}})

		})
	})
}
