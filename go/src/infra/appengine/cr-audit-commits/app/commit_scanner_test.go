// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/server/router"
)

func TestCommitScanner(t *testing.T) {

	Convey("CommitScanner handler test", t, func() {
		ctx := memory.Use(context.Background())

		scannerPath := "/_cron/commitscanner"

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			datastore.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.GET(scannerPath, router.NewMiddlewareChain(withTestingContext), CommitScanner)
		srv := httptest.NewServer(r)
		client := &http.Client{}
		testClients = &Clients{}
		Convey("Unknown Repo", func() {
			resp, err := client.Get(srv.URL + scannerPath + "?repo=unknown")
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, 400)

		})
		Convey("New Repo", func() {
			RuleMap["new-repo"] = &RepoConfig{
				BaseRepoURL:    "https://new.googlesource.com/new.git",
				GerritURL:      "https://new-review.googlesource.com",
				BranchName:     "master",
				StartingCommit: "000000",
				Rules: []RuleSet{AccountRules{
					Account: "new@test.com",
					Funcs: []RuleFunc{func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
						return &RuleResult{"Dummy rule", rulePassed, ""}
					}},
				}},
			}
			Convey("No revisions", func() {
				testClients.gitiles = mockGitilesClient{}
				resp, err := client.Get(srv.URL + scannerPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://new.googlesource.com/new.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "000000")
			})
			Convey("No interesting revisions", func() {
				testClients.gitiles = mockGitilesClient{
					r: []gitiles.Commit{{Commit: "abcdef000123123"}},
				}
				resp, err := client.Get(srv.URL + scannerPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://new.googlesource.com/new.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "abcdef000123123")
			})
			Convey("Interesting revisions", func() {
				testClients.gitiles = mockGitilesClient{
					r: []gitiles.Commit{
						{
							Commit: "006a006a",
							Author: gitiles.User{
								Email: "new@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
							Committer: gitiles.User{
								Email: "new@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
						},
						{
							Commit: "c001c0de",
							Author: gitiles.User{
								Email: "new@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
							Committer: gitiles.User{
								Email: "new@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
						},
						{Commit: "deadbeef"},
					},
				}
				resp, err := client.Get(srv.URL + scannerPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://new.googlesource.com/new.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "deadbeef")
				So(rs.LastRelevantCommit, ShouldEqual, "c001c0de")
				rc := &RelevantCommit{
					RepoStateKey: datastore.KeyForObj(ctx, rs),
					CommitHash:   "c001c0de",
				}
				err = datastore.Get(ctx, rc)
				So(err, ShouldBeNil)
				So(rc.PreviousRelevantCommit, ShouldEqual, "006a006a")
			})
		})
		Convey("Old Repo", func() {
			RuleMap["old-repo"] = &RepoConfig{
				BaseRepoURL:    "https://old.googlesource.com/old.git",
				GerritURL:      "https://old-review.googlesource.com",
				BranchName:     "master",
				StartingCommit: "000000",
				Rules: []RuleSet{AccountRules{
					Account: "old@test.com",
					Funcs: []RuleFunc{func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
						return &RuleResult{"Dummy rule", rulePassed, ""}
					}},
				}},
			}
			datastore.Put(ctx, &RepoState{
				RepoURL:            "https://old.googlesource.com/old.git/+/master",
				LastKnownCommit:    "123456",
				LastRelevantCommit: "999999",
			})

			Convey("No interesting revisions", func() {
				testClients.gitiles = mockGitilesClient{
					r: []gitiles.Commit{{Commit: "abcdef000123123"}},
				}
				resp, err := client.Get(srv.URL + scannerPath + "?repo=old-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://old.googlesource.com/old.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "abcdef000123123")
				So(rs.LastRelevantCommit, ShouldEqual, "999999")
			})
			Convey("Interesting revisions", func() {
				testClients.gitiles = mockGitilesClient{
					r: []gitiles.Commit{
						{
							Commit: "c001c0de",
							Author: gitiles.User{
								Email: "old@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
							Committer: gitiles.User{
								Email: "old@test.com",
								Time:  "Sun Sep 03 00:56:34 2017",
							},
						},
						{Commit: "deadbeef"},
					},
				}
				resp, err := client.Get(srv.URL + scannerPath + "?repo=old-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://old.googlesource.com/old.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "deadbeef")
				So(rs.LastRelevantCommit, ShouldEqual, "c001c0de")
				rc := &RelevantCommit{
					RepoStateKey: datastore.KeyForObj(ctx, rs),
					CommitHash:   "c001c0de",
				}
				err = datastore.Get(ctx, rc)
				So(err, ShouldBeNil)
				So(rc.PreviousRelevantCommit, ShouldEqual, "999999")
			})
		})
		srv.Close()
	})
}
