// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
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
)

func TestTBRRules(t *testing.T) {
	// TODO(crbug.com/798843): Uncomment this and make the tests not racy.
	//t.Parallel()

	Convey("TBR Rules", t, func() {
		ctx := memory.Use(context.Background())
		datastore.GetTestable(ctx).CatchupIndexes()
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:     datastore.KeyForObj(ctx, rs),
			CommitHash:       "7b12c0de1",
			Status:           auditScheduled,
			CommitTime:       time.Date(2017, time.August, 25, 15, 0, 0, 0, time.UTC),
			CommitterAccount: "jdoe@sample.com",
			AuthorAccount:    "jdoe@sample.com",
			CommitMessage:    "Revert security fix, TBR=someone",
		}
		cfg := &RepoConfig{
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "master",
		}
		ap := &AuditParams{
			TriggeringAccount: "jdoe@sample.com",
			RepoCfg:           cfg,
		}
		reviewedcl := &gerrit.Change{
			ChangeID:        "tbrchangeid1",
			ChangeNumber:    4321,
			CurrentRevision: "7b12c0de1",
			Owner: gerrit.AccountInfo{
				AccountID: 1337,
			},

			Labels: map[string]gerrit.LabelInfo{
				"Code-Review": {
					All: []gerrit.VoteInfo{
						{
							AccountInfo: gerrit.AccountInfo{
								AccountID: 1337,
							},
							Value: 1,
						},
						{
							AccountInfo: gerrit.AccountInfo{
								AccountID: 4001,
							},
							Value: 1,
						},
					},
					Values: map[string]string{
						"-1": "No",
						" 0": "Whatever",
						"+1": "Yes",
					},
				},
			},
		}
		notreviewedcl := &gerrit.Change{
			ChangeID:        "tbrchangeid2",
			ChangeNumber:    4322,
			CurrentRevision: "7b12c0de2",
			Owner: gerrit.AccountInfo{
				AccountID: 1337,
			},
			Labels: map[string]gerrit.LabelInfo{
				"Code-Review": {
					All: []gerrit.VoteInfo{
						{
							AccountInfo: gerrit.AccountInfo{
								AccountID: 1337,
							},
							Value: 1,
						},
					},
					Values: map[string]string{
						"-1": "No",
						" 0": "Whatever",
						"+1": "Yes",
					},
				},
			},
		}
		q := map[string][]*gerrit.Change{
			"commit:7b12c0de1": {reviewedcl},
			"commit:7b12c0de2": {notreviewedcl},
		}
		testClients := &Clients{}
		testClients.gerrit = &mockGerritClient{q: q}

		expectedStatus := rulePassed
		var gerritCalls []string

		Convey("Pass", func() {
			// Inject gitiles response.
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "7b12c0de1",
				PageSize:   1,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "7b12c0de1",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
				},
			}, nil)
			rr := ChangeReviewed{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, expectedStatus)

		})
		Convey("Non-Pass", func() {
			Convey("Fail", func() {
				rc.CommitHash = "7b12c0de2"
				expectedStatus = ruleFailed
			})

			Convey("Pending - no notification", func() {
				rc.CommitHash = "7b12c0de2"
				rc.CommitTime = time.Now().Add(-23 * time.Hour)
				expectedStatus = rulePending

			})
			Convey("Pending - send notification", func() {
				rc.CommitHash = "7b12c0de2"
				rc.CommitTime = time.Now().Add(-25 * time.Hour)
				rc.Result = append(rc.Result, RuleResult{
					RuleName:         "ChangeReviewed",
					RuleResultStatus: rulePending,
				})
				expectedStatus = rulePending
				gerritCalls = []string{"SetReview"}

			})
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "7b12c0de2",
				PageSize:   1,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "7b12c0de2",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
				},
			}, nil)
			rr := ChangeReviewed{}.Run(ctx, ap, rc, testClients)
			So(rr.RuleResultStatus, ShouldEqual, expectedStatus)
			So(testClients.gerrit.(*mockGerritClient).calls, ShouldResemble, gerritCalls)
		})
		Convey("Skip", func() {
			expectedStatus = ruleSkipped
			rc.AuthorAccount = "recipe-mega-autoroller@chops-service-accounts.iam.gserviceaccount.com"
			// Inject gitiles response.
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "7b12c0de1",
				PageSize:   1,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "7b12c0de1",
						Committer: &git.Commit_User{
							Time: mustGitilesTime("Fri Aug 25 07:00:00 2017"),
						},
					},
				},
			}, nil)
			rr := ChangeReviewed{}.Run(ctx, ap, rc, testClients)
			// Check result code.
			So(rr.RuleResultStatus, ShouldEqual, expectedStatus)

		})
	})
}
