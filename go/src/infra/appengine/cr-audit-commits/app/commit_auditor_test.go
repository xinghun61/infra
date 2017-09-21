// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"

	"infra/monorail"
)

func TestCommitAuditor(t *testing.T) {
	// This tests cannot be parallelized as they mutate the static config
	// that is stored in a global.
	Convey("CommitAuditor handler test", t, func() {
		ctx := memory.Use(context.Background())

		auditorPath := "/_cron/commitauditor"

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			ds.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.GET(auditorPath, router.NewMiddlewareChain(withTestingContext), CommitAuditor)
		srv := httptest.NewServer(r)
		client := &http.Client{}
		testClients = &Clients{}
		testClients.monorail = mockMonorailClient{
			il: &monorail.IssuesListResponse{},
			ii: &monorail.InsertIssueResponse{
				Issue: &monorail.Issue{
					Id: 12345,
				},
			},
		}
		// Save repoconfig
		// make sure there is a rule that always passes.
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
		repoState := &RepoState{
			RepoURL:            "https://new.googlesource.com/new.git/+/master",
			LastKnownCommit:    "222222",
			LastRelevantCommit: "222222",
		}
		err := ds.Put(ctx, repoState)
		rsk := ds.KeyForObj(ctx, repoState)

		So(err, ShouldBeNil)

		Convey("No commits", func() {
			resp, err := client.Get(srv.URL + auditorPath + "?repo=new-repo")
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, 200)
		})
		Convey("With commits", func() {
			for i := 0; i < 10; i++ {
				rc := &RelevantCommit{
					RepoStateKey:  rsk,
					CommitHash:    fmt.Sprintf("%02d%02d%02d", i, i, i),
					Status:        auditScheduled,
					AuthorAccount: "new@test.com",
				}
				err := ds.Put(ctx, rc)
				So(err, ShouldBeNil)
			}
			Convey("All pass", func() {
				resp, err := client.Get(srv.URL + auditorPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				for i := 0; i < 10; i++ {
					rc := &RelevantCommit{
						RepoStateKey: rsk,
						CommitHash:   fmt.Sprintf("%02d%02d%02d", i, i, i),
					}
					err := ds.Get(ctx, rc)
					So(err, ShouldBeNil)
					So(rc.Status, ShouldEqual, auditCompleted)
				}
			})
			Convey("Some fail", func() {
				RuleMap["new-repo"].Rules[0].(AccountRules).Funcs[0] = func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
					return &RuleResult{"Dummy rule", ruleFailed, ""}
				}
				resp, err := client.Get(srv.URL + auditorPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				for i := 0; i < 10; i++ {
					rc := &RelevantCommit{
						RepoStateKey: rsk,
						CommitHash:   fmt.Sprintf("%02d%02d%02d", i, i, i),
					}
					err := ds.Get(ctx, rc)
					So(err, ShouldBeNil)
					So(rc.Status, ShouldEqual, auditCompletedWithViolation)
				}
			})
			Convey("Some panic", func() {
				RuleMap["new-repo"].Rules[0].(AccountRules).Funcs[0] = func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
					if rc.Status == auditScheduled {
						panic("This always panics")
					}
					return &RuleResult{"Dummy rule", ruleFailed, ""}
				}
				resp, err := client.Get(srv.URL + auditorPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				for i := 0; i < 10; i++ {
					rc := &RelevantCommit{
						RepoStateKey: rsk,
						CommitHash:   fmt.Sprintf("%02d%02d%02d", i, i, i),
					}
					err := ds.Get(ctx, rc)
					So(err, ShouldBeNil)
					So(rc.Status, ShouldEqual, auditScheduled)
					So(rc.Retries, ShouldEqual, 1)
				}
			})
		})
		srv.Close()
	})
}
