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
	"google.golang.org/genproto/protobuf/field_mask"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
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
			CommitMessage:    "Sample Failed Build: https://ci/buildbot/m/b/42",
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
		buildbucketMockClient := buildbucketpb.NewMockBuildsClient(gomock.NewController(t))
		testClients.buildbucketFactory = func(httpClient *http.Client) buildbucketpb.BuildsClient {
			return buildbucketMockClient
		}

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
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
			}).Return(&buildbucketpb.Build{
				Input: &buildbucketpb.Build_Input{
					GitilesCommit: &buildbucketpb.GitilesCommit{
						Project: "a",
						Id:      "c001c0de",
					},
				},
			}, nil)

			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 41,
			}).Return(&buildbucketpb.Build{
				Input: &buildbucketpb.Build_Input{
					GitilesCommit: &buildbucketpb.GitilesCommit{
						Project: "a",
						Id:      "01dc0de",
					},
				},
			}, nil)

			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:            "a",
				Committish:         "c001c0de",
				ExcludeAncestorsOf: "01dc0de",
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "c001c0de",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
					{
						Id: "badc0de",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 06:00:00 2017"),
						},
					},
				},
			}, nil)
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Culprit not in build", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
			}).Return(&buildbucketpb.Build{
				Input: &buildbucketpb.Build_Input{
					GitilesCommit: &buildbucketpb.GitilesCommit{
						Project: "a",
						Id:      "c001c0de",
					},
				},
			}, nil)

			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 41,
			}).Return(&buildbucketpb.Build{
				Input: &buildbucketpb.Build_Input{
					GitilesCommit: &buildbucketpb.GitilesCommit{
						Project: "a",
						Id:      "01dc0de",
					},
				},
			}, nil)

			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:            "a",
				Committish:         "c001c0de",
				ExcludeAncestorsOf: "01dc0de",
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "c001c0de",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
					// Culprit absent.
				},
			}, nil)
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "not found in changes for build")

		})
		Convey("Culprit not in build - flake", func() {
			rc.CommitMessage = rc.CommitMessage + "\nSample Flaky Test: dummy_test"
			rr := CulpritInBuild{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleSkipped)

		})
		Convey("Failed build is compile failure Pass", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "compile",
						Status: buildbucketpb.Status_FAILURE,
					},
				},
			}, nil)
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Failed build is compile failure Pass - Nested", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "Nesting step|compile",
						Status: buildbucketpb.Status_FAILURE,
					},
				},
			}, nil)
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Failed build is compile failure Fail", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "compile",
						Status: buildbucketpb.Status_SUCCESS,
					},
				},
			}, nil)
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not have an expected failure")
			So(rr.Message, ShouldContainSubstring, "compile")
		})
		Convey("Failed build is compile failure Fail - missing step", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "No-op (compilation skipped)",
						Status: buildbucketpb.Status_FAILURE,
					},
				},
			}, nil)
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, "does not have an expected failure")
			So(rr.Message, ShouldContainSubstring, "compile")
		})
		Convey("Failed build is flaky failure Pass", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "dummy_step",
						Status: buildbucketpb.Status_FAILURE,
					},
				},
			}, nil)
			rc.CommitMessage = rc.CommitMessage + "\nSample Failed Step: dummy_step\nSample Flaky Test: dummy_test"
			rr := FailedBuildIsAppropriateFailure{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Failed build is flaky failure Fail", func() {
			buildbucketMockClient.EXPECT().GetBuild(gomock.Any(), &buildbucketpb.GetBuildRequest{
				Builder: &buildbucketpb.BuilderID{
					Project: "chromium",
					Bucket:  "ci",
					Builder: "b",
				},
				BuildNumber: 42,
				Fields:      &field_mask.FieldMask{Paths: []string{"steps"}},
			}).Return(&buildbucketpb.Build{
				Steps: []*buildbucketpb.Step{
					{
						Name:   "different_dummy_step",
						Status: buildbucketpb.Status_FAILURE,
					},
				},
			}, nil)
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
