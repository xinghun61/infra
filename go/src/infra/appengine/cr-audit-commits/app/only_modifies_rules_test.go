// Copyright 2017 The Chromium Authors. All rights reserved.
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
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

func TestOnlyModifiesPaths(t *testing.T) {
	t.Parallel()

	Convey("OnlyModifiesPaths rules work", t, func() {
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
			CommitterAccount: "releasebot@sample.com",
			AuthorAccount:    "releasebot@sample.com",
			CommitMessage:    "Bumping version to Foo",
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

		Convey("Only modifies file", func() {
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
								OldPath: "somefile",
								NewPath: "somefile",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name:  "ruleName",
				files: []string{"somefile"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")

		})
		Convey("Only modifies dir", func() {
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
								OldPath: "somedir/myfile",
								NewPath: "somedir/newfile",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name: "ruleName",
				dirs: []string{"somedir"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")

		})
		Convey("Only modifies files+dirs", func() {
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
								OldPath: "a.txt",
								NewPath: "a.txt",
							},
							{
								Type:    git.Commit_TreeDiff_MODIFY,
								OldPath: "mydir/a.txt",
								NewPath: "mydir/a.txt",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name:  "ruleName",
				dirs:  []string{"mydir"},
				files: []string{"a.txt"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")

		})
		Convey("Modifies unexpected file", func() {
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
								OldPath: "a.txt",
								NewPath: "b.txt",
							},
							{
								Type:    git.Commit_TreeDiff_MODIFY,
								OldPath: "mydir/a.txt",
								NewPath: "mydir/a.txt",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name:  "ruleName",
				dirs:  []string{"mydir"},
				files: []string{"a.txt"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
		})
		Convey("Confuse dir check", func() {
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
								OldPath: "a.txt",
								NewPath: "b.txt",
							},
							{
								Type:    git.Commit_TreeDiff_MODIFY,
								OldPath: "mydir",
								NewPath: "mydir",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name:  "ruleName",
				dirs:  []string{"mydir"},
				files: []string{"a.txt"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
		})
		Convey("Adds a file in whitelisted dir", func() {
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
								Type:    git.Commit_TreeDiff_ADD,
								OldPath: "",
								NewPath: "somedir/somefile",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name: "ruleName",
				dirs: []string{"somedir"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")
		})
		Convey("Deletes a file in whitelisted dir", func() {
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
								Type:    git.Commit_TreeDiff_DELETE,
								OldPath: "somedir/somefile",
								NewPath: "",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name: "ruleName",
				dirs: []string{"somedir"},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")
		})
	})
}

func TestReleaseBotRules(t *testing.T) {
	t.Parallel()

	Convey("ReleaseBot rules work", t, func() {
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
			CommitterAccount: "releasebot@sample.com",
			AuthorAccount:    "releasebot@sample.com",
			CommitMessage:    "Bumping version to Foo",
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

		Convey("Only modifies version", func() {
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
								OldPath: "chrome/VERSION",
								NewPath: "chrome/VERSION",
							},
						},
					},
				},
			}, nil)
			// Run rule
			rr := OnlyModifiesFilesAndDirsRule{
				name: "OnlyModifiesReleaseFiles",
				files: []string{
					"chrome/MAJOR_BRANCH_DATE",
					"chrome/VERSION",
				},
			}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
			So(rr.Message, ShouldEqual, "")

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
									OldPath: "chrome/VERSION",
									NewPath: "chrome/VERSION",
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
				rr := OnlyModifiesFilesAndDirsRule{
					name: "OnlyModifiesReleaseFiles",
					files: []string{
						"chrome/MAJOR_BRANCH_DATE",
						"chrome/VERSION",
					},
				}.Run(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})
			Convey("Renames VERSION", func() {
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
									OldPath: "chrome/VERSION",
									NewPath: "chrome/VERSION.bak",
								},
							},
						},
					},
				}, nil)
				// Run rule
				rr := OnlyModifiesFilesAndDirsRule{
					name: "OnlyModifiesReleaseFiles",
					files: []string{
						"chrome/MAJOR_BRANCH_DATE",
						"chrome/VERSION",
					},
				}.Run(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})

		})
	})
}
