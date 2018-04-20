// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"golang.org/x/net/context"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"
)

func TestCommitAuditor(t *testing.T) {

	Convey("Auditor handler test", t, func() {
		ctx := memory.Use(context.Background())

		auditorPath := "/_task/auditor"

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			ds.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.GET(auditorPath, router.NewMiddlewareChain(withTestingContext), Auditor)
		srv := httptest.NewServer(r)
		client := &http.Client{}
		testClients = &Clients{}
		Convey("Unknown Ref", func() {
			resp, err := client.Get(srv.URL + auditorPath + "?refUrl=unknown")
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, 400)

		})
		Convey("Dummy Repo", func() {
			RuleMap["dummy-repo"] = &RepoConfig{
				BaseRepoURL:    "https://dummy.googlesource.com/dummy.git",
				GerritURL:      "https://dummy-review.googlesource.com",
				BranchName:     "refs/heads/master",
				StartingCommit: "000000",
				Rules: map[string]RuleSet{"rules": AccountRules{
					Account: "dummy@test.com",
					Funcs: []RuleFunc{func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
						return &RuleResult{"Dummy rule", rulePassed, "", ""}
					}},
					notificationFunction: dummyNotifier,
				}},
			}
			escapedRepoURL := url.QueryEscape("https://dummy.googlesource.com/dummy.git/+/refs/heads/master")
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}

			Convey("Test auditing", func() {
				repoState := &RepoState{
					ConfigName:         "dummy-repo",
					RepoURL:            "https://dummy.googlesource.com/dummy.git/+/refs/heads/master",
					LastKnownCommit:    "222222",
					LastRelevantCommit: "222222",
				}
				err := ds.Put(ctx, repoState)
				rsk := ds.KeyForObj(ctx, repoState)

				So(err, ShouldBeNil)
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "dummy",
					Treeish:  "refs/heads/master",
					Ancestor: "222222",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{},
				}, nil)

				Convey("No commits", func() {
					resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
					So(err, ShouldBeNil)
					So(resp.StatusCode, ShouldEqual, 200)
				})
				Convey("With commits", func() {
					for i := 0; i < 10; i++ {
						rc := &RelevantCommit{
							RepoStateKey:  rsk,
							CommitHash:    fmt.Sprintf("%02d%02d%02d", i, i, i),
							Status:        auditScheduled,
							AuthorAccount: "dummy@test.com",
						}
						err := ds.Put(ctx, rc)
						So(err, ShouldBeNil)
					}
					Convey("All pass", func() {
						resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
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
						RuleMap["dummy-repo"].Rules["rules"].(AccountRules).Funcs[0] = func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
							return &RuleResult{"Dummy rule", ruleFailed, "", ""}
						}
						resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
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
						RuleMap["dummy-repo"].Rules["rules"].(AccountRules).Funcs[0] = func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
							if rc.Status == auditScheduled {
								panic("This always panics")
							}
							return &RuleResult{"Dummy rule", ruleFailed, "", ""}
						}
						resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
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
			})
			srv.Close()
		})
	})
}
