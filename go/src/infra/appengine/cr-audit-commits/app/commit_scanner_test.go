// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/ptypes"
	google_protobuf "github.com/golang/protobuf/ptypes/timestamp"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"
)

func mustGitilesTime(v string) *google_protobuf.Timestamp {
	var t time.Time
	t, err := time.Parse(time.ANSIC, v)
	if err != nil {
		t, err = time.Parse(time.ANSIC+" -0700", v)
	}
	if err != nil {
		panic(fmt.Errorf("could not parse time %q: %v", v, err))

	}
	r, err := ptypes.TimestampProto(t)
	if err != nil {
		panic(fmt.Errorf("could not convert time %s to google_protobuf.Timestamp: %v", t, err))

	}
	return r
}

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
				Rules: map[string]RuleSet{"rules": AccountRules{
					Account: "new@test.com",
					Funcs: []RuleFunc{func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
						return &RuleResult{"Dummy rule", rulePassed, "", ""}
					}},
					notificationFunction: fileBugForFinditViolation,
				}},
			}
			Convey("No revisions", func() {
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "new",
					Treeish:  "master",
					Ancestor: "000000",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{}, nil)
				resp, err := client.Get(srv.URL + scannerPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://new.googlesource.com/new.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "000000")
			})
			Convey("No interesting revisions", func() {
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "new",
					Treeish:  "master",
					Ancestor: "000000",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{{Id: "abcdef000123123"}},
				}, nil)
				resp, err := client.Get(srv.URL + scannerPath + "?repo=new-repo")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				rs := &RepoState{RepoURL: "https://new.googlesource.com/new.git/+/master"}
				err = datastore.Get(ctx, rs)
				So(err, ShouldBeNil)
				So(rs.LastKnownCommit, ShouldEqual, "abcdef000123123")
			})
			Convey("Interesting revisions", func() {
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "new",
					Treeish:  "master",
					Ancestor: "000000",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{
						{Id: "deadbeef"},
						{
							Id: "c001c0de",
							Author: &git.Commit_User{
								Email: "new@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
							Committer: &git.Commit_User{
								Email: "new@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
						},
						{
							Id: "006a006a",
							Author: &git.Commit_User{
								Email: "new@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
							Committer: &git.Commit_User{
								Email: "new@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
						},
					},
				}, nil)
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
				Rules: map[string]RuleSet{"rules": AccountRules{
					Account: "old@test.com",
					Funcs: []RuleFunc{func(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
						return &RuleResult{"Dummy rule", rulePassed, "", ""}
					}},
					notificationFunction: fileBugForFinditViolation,
				}},
			}
			datastore.Put(ctx, &RepoState{
				RepoURL:            "https://old.googlesource.com/old.git/+/master",
				LastKnownCommit:    "123456",
				LastRelevantCommit: "999999",
			})

			Convey("No interesting revisions", func() {
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "old",
					Treeish:  "master",
					Ancestor: "123456",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{{Id: "abcdef000123123"}},
				}, nil)
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
				gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
				testClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
					return gitilesMockClient, nil
				}
				gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
					Project:  "old",
					Treeish:  "master",
					Ancestor: "123456",
					PageSize: 6000,
				}).Return(&gitilespb.LogResponse{
					Log: []*git.Commit{
						{Id: "deadbeef"},
						{
							Id: "c001c0de",
							Author: &git.Commit_User{
								Email: "old@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
							Committer: &git.Commit_User{
								Email: "old@test.com",
								Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
							},
						},
					},
				}, nil)
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
