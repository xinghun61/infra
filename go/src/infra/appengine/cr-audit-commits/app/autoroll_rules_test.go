// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"net/http"
	"testing"
	"time"

	"context"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

func TestAutoRollRules(t *testing.T) {
	Convey("AutoRoll rules work", t, func() {
		ctx := memory.Use(context.Background())
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:     datastore.KeyForObj(ctx, rs),
			CommitHash:       "b07c0de",
			Status:           auditScheduled,
			CommitTime:       time.Date(2017, time.August, 25, 15, 0, 0, 0, time.UTC),
			CommitterAccount: "autoroller@sample.com",
			AuthorAccount:    "autoroller@sample.com",
			CommitMessage:    "Roll dep ABC..XYZ",
		}
		cfg := &RepoConfig{
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "master",
		}
		ap := &AuditParams{
			TriggeringAccount: "releasebot@sample.com",
			RepoCfg:           cfg,
		}
		testClients := &Clients{}

		Convey("Only modifies DEPS", func() {
			// Inject gitiles log response
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
				Project:    "a",
				Committish: "b07c0de",
				PageSize:   1,
				TreeDiff:   true,
			}).Return(&gitilespb.LogResponse{
				Log: []*git.Commit{
					{
						Id: "b07c0de",
						TreeDiff: []*git.Commit_TreeDiff{
							{
								Type:    git.Commit_TreeDiff_MODIFY,
								OldPath: "DEPS",
								NewPath: "DEPS",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := AutoRollRulesDEPS(rc.CommitterAccount).Rules[0].Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Introduces unexpected changes", func() {
			Convey("Modifies other file", func() {
				// Inject gitiles log response
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:    "a",
					Committish: "b07c0de",
					PageSize:   1,
					TreeDiff:   true,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{
						{
							Id: "b07c0de",
							TreeDiff: []*git.Commit_TreeDiff{
								{
									Type:    git.Commit_TreeDiff_MODIFY,
									OldPath: "DEPS",
									NewPath: "DEPS",
								},
								{
									Type:    git.Commit_TreeDiff_ADD,
									NewPath: "other/path",
								},
							},
						},
					},
				}, nil)
				// Run rule
				rr := AutoRollRulesDEPS(rc.CommitterAccount).Rules[0].Run(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})
			Convey("Renames DEPS", func() {
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:    "a",
					Committish: "b07c0de",
					PageSize:   1,
					TreeDiff:   true,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{
						{
							Id: "b07c0de",
							TreeDiff: []*git.Commit_TreeDiff{
								{
									Type:    git.Commit_TreeDiff_RENAME,
									OldPath: "DEPS",
									NewPath: "DEPS.bak",
								},
							},
						},
					},
				}, nil)
				// Run rule
				rr := AutoRollRulesDEPS(rc.CommitterAccount).Rules[0].Run(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})

		})
	})
}
