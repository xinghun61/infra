// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"testing"
	"time"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gitiles"
)

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
		testClients = &Clients{}

		Convey("Only modifies version", func() {
			// Inject gitiles log response
			r := []gitiles.Commit{
				{
					Commit: "b07c0de",
					TreeDiff: []gitiles.TreeDiff{
						{
							Type:    "modify",
							OldPath: "chrome/VERSION",
							NewPath: "chrome/VERSION",
						},
					},
				},
			}
			testClients.gitiles = &mockGitilesClient{r: r}
			// Run rule
			rr := OnlyModifiesVersionFile(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Introduces unexpected changes", func() {
			Convey("Modifies other file", func() {
				r := []gitiles.Commit{
					{
						Commit: "b07c0de",
						TreeDiff: []gitiles.TreeDiff{
							{
								Type:    "modify",
								OldPath: "chrome/VERSION",
								NewPath: "chrome/VERSION",
							},
							{
								Type:    "add",
								NewPath: "other/path",
							},
						},
					},
				}
				testClients.gitiles = &mockGitilesClient{r: r}
				// Run rule
				rr := OnlyModifiesVersionFile(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})
			Convey("Renames VERSION", func() {
				r := []gitiles.Commit{
					{
						Commit: "b07c0de",
						TreeDiff: []gitiles.TreeDiff{
							{
								Type:    "rename",
								OldPath: "chrome/VERSION",
								NewPath: "chrome/VERSION.bak",
							},
						},
					},
				}
				testClients.gitiles = &mockGitilesClient{r: r}
				// Run rule
				rr := OnlyModifiesVersionFile(ctx, ap, rc, testClients)
				// Check result code
				So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			})

		})
	})
}
