// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"errors"
	"fmt"
	"net/http"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"

	buildbot "infra/monitoring/messages"
)

func TestFinditRules(t *testing.T) {
	// TODO(crbug.com/798843): Uncomment this and make the tests not racy.
	//t.Parallel()

	Convey("Findit rules work", t, func() {
		ctx := memory.Use(context.Background())
		datastore.GetTestable(ctx).CatchupIndexes()
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:     datastore.KeyForObj(ctx, rs),
			CommitHash:       "12ebe127",
			Status:           auditScheduled,
			CommitTime:       time.Date(2017, time.August, 25, 15, 0, 0, 0, time.UTC),
			CommitterAccount: "findit@sample.com",
			AuthorAccount:    "findit@sample.com",
			CommitMessage:    "Sample Failed Build: https://ci/fake/build",
		}
		cfg := &RepoConfig{
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "master",
		}
		ap := &AuditParams{
			TriggeringAccount: "findit@sample.com",
			RepoCfg:           cfg,
		}
		rvc := &gerrit.Change{
			ChangeID: "revertcid",
			RevertOf: 666,
		}
		cc := &gerrit.Change{
			ChangeID:        "culpritcid",
			ChangeNumber:    666,
			CurrentRevision: "badc0de",
		}
		bad := &gerrit.Change{
			ChangeID: "badcid",
			RevertOf: 666,
		}
		q := map[string][]*gerrit.Change{
			"commit:12ebe127":  {rvc},
			"revertcid":        {rvc},
			"666":              {cc},
			"commit:badbadbad": {bad},
			"badcid":           {bad},
		}
		pr := map[string]bool{
			"revertcid": true,
		}
		testClients := &Clients{}
		testClients.gerrit = &mockGerritClient{q: q, pr: pr}

		Convey("Culprit age Pass", func() {
			// Inject gitiles response.
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "badc0de",
				PageSize:   1,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "badc0de",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
				},
			}, nil)
			rr := CulpritAge{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Culprit age Fail", func() {
			// Inject gitiles response.
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "badc0de",
				PageSize:   1,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "badc0de",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 18 07:00:00 2017"),
						},
					},
				},
			}, nil)
			// Run rule.
			rr := CulpritAge{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)

		})
		Convey("Only commits own change Pass", func() {
			// Run rule.
			rr := OnlyCommitsOwnChange{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Only commits own change Pass (someone else commits)", func() {
			rc.CommitterAccount = "bad-dude@creepy.domain"
			// Run rule.
			rr := OnlyCommitsOwnChange{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Only commits own change Fail", func() {
			rc.AuthorAccount = "bad-dude@creepy.domain"
			// Run rule.
			rr := OnlyCommitsOwnChange{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)

		})
		Convey("Culprit age Error", func() {
			// Inject gitiles error.
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "badc0de",
				PageSize:   1,
			}).Return(nil, errors.New("Some error"))

			// Run rule.
			rr := func() {
				CulpritAge{}.Run(ctx, ap, rc, testClients)
			}
			// Check result code.
			So(rr, ShouldPanic)
		})
		Convey("Auto-reverts per day Pass", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoRevertsPerDay, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "cq@other.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoRevertsPerDay{}.Run(ctx, ap, rcs[0], testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Auto-reverts per day Failed", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoRevertsPerDay+1, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "cq@other.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoRevertsPerDay{}.Run(ctx, ap, rcs[0], testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, fmt.Sprintf("%d commits were created", MaxAutoRevertsPerDay+1))
		})
		Convey("Auto-commits per day Pass", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoCommitsPerDay, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "findit@sample.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoCommitsPerDay{}.Run(ctx, ap, rcs[0], testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Auto-commits per day Failed", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoCommitsPerDay+1, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "findit@sample.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoCommitsPerDay{}.Run(ctx, ap, rcs[0], testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, fmt.Sprintf("%d commits were committed", MaxAutoCommitsPerDay+1))
		})

		Convey("Culprit in build", func() {
			fakeBuild := &buildbot.Build{}
			fakeBuild.SourceStamp.Changes = []buildbot.Change{
				{Revision: "dummy"},
				{Revision: "badc0de"},
			}
			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Culprit not in build", func() {
			fakeBuild := &buildbot.Build{}
			fakeBuild.SourceStamp.Changes = []buildbot.Change{
				{Revision: "dummy"},
			}
			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "not found in changes for build")

		})
		Convey("Culprit not in build - flake", func() {
			fakeBuild := &buildbot.Build{}
			fakeBuild.SourceStamp.Changes = []buildbot.Change{
				{Revision: "dummy"},
			}
			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rc.CommitMessage = rc.CommitMessage + "\nSample Flaky Test: dummy_test"
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleSkipped)

		})
		Convey("Failed build is compile failure Pass", func() {
			fakeBuild := &buildbot.Build{}
			fakeUpdateStep := buildbot.Step{}
			fakeUpdateStep.Name = "update_scripts"
			fakeUpdateStep.Results = []interface{}{0.0, 0}

			fakeCompileStep := buildbot.Step{}
			fakeCompileStep.Name = "compile"
			fakeCompileStep.Results = []interface{}{2.0, 0}
			fakeBuild.Steps = []buildbot.Step{fakeUpdateStep, fakeCompileStep}

			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Failed build is compile failure Fail", func() {
			fakeBuild := &buildbot.Build{}
			// This Step fails, but the rule shouldn't care.
			fakeUpdateStep := buildbot.Step{}
			fakeUpdateStep.Name = "update_scripts"
			fakeUpdateStep.Results = []interface{}{2.0, 0}

			// This compile step had warnings but did not fail.
			fakeCompileStep := buildbot.Step{}
			fakeCompileStep.Name = "compile"
			fakeCompileStep.Results = []interface{}{1.0, 0}
			fakeBuild.Steps = []buildbot.Step{fakeUpdateStep, fakeCompileStep}

			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not have an expected failure")
			So(rr.Message, ShouldContainSubstring, "compile")
		})
		Convey("Failed build is flaky failure Pass", func() {
			fakeBuild := &buildbot.Build{}
			fakeUpdateStep := buildbot.Step{}
			fakeUpdateStep.Name = "update_scripts"
			fakeUpdateStep.Results = []interface{}{0.0, 0}

			fakeDummyStep := buildbot.Step{}
			fakeDummyStep.Name = "dummy_step"
			fakeDummyStep.Results = []interface{}{2.0, 0}
			fakeBuild.Steps = []buildbot.Step{fakeUpdateStep, fakeDummyStep}

			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rc.CommitMessage = rc.CommitMessage + "\nSample Failed Step: dummy_step\nSample Flaky Test: dummy_test"
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Failed build is flaky failure Fail", func() {
			fakeBuild := &buildbot.Build{}
			// This Step fails, but the rule shouldn't care.
			fakeUpdateStep := buildbot.Step{}
			fakeUpdateStep.Name = "update_scripts"
			fakeUpdateStep.Results = []interface{}{2.0, 0}

			// This dummy step had warnings but did not fail.
			fakeDummyStep := buildbot.Step{}
			fakeDummyStep.Name = "dummy_step"
			fakeDummyStep.Results = []interface{}{1.0, 0}
			fakeBuild.Steps = []buildbot.Step{fakeUpdateStep, fakeDummyStep}

			testClients.milo = mockMiloClient{q: map[string]*buildbot.Build{
				"https://ci/fake/build": fakeBuild,
			}}
			rc.CommitMessage = rc.CommitMessage + "\nSample Failed Step: dummy_step\nSample Flaky Test: dummy_test"
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not have an expected failure")
			So(rr.Message, ShouldContainSubstring, "dummy_step")
		})
		Convey("RevertOfCulprit Pass", func() {
			rc.CommitMessage = "This reverts commit badc0de\n" + rc.CommitMessage
			rr := RevertOfCulprit{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("RevertOfCulprit Fail - revert, but not pure", func() {
			rc.CommitMessage = "This reverts commit badc0de\n" + rc.CommitMessage
			rc.CommitHash = "badbadbad"
			rr := RevertOfCulprit{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "*pure* revert")
		})
		Convey("RevertOfCulprit Fail - not revert", func() {
			testClients.gerrit.(*mockGerritClient).q["commit:12ebe127"][0].RevertOf = 0
			rr := RevertOfCulprit{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not appear to be a revert")
		})
		Convey("RevertOfCulprit Fail - culprit not in revert commit message", func() {
			rr := RevertOfCulprit{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not include the revision it reverts")
		})
	})
}
