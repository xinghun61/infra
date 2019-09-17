// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"context"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/ptypes"
	google_protobuf "github.com/golang/protobuf/ptypes/timestamp"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"
)

type panicRule struct{}

// GetName returns the name of the rule.
func (rule panicRule) GetName() string {
	return "Dummy Rule"
}

// Run panics if the commit hasn't been audited.
func (rule panicRule) Run(c context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	if rc.Status == auditScheduled {
		panic("This always panics")
	}
	return &RuleResult{"Dummy rule", ruleFailed, "", ""}
}

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

func dummyNotifier(ctx context.Context, cfg *RepoConfig, rc *RelevantCommit, cs *Clients, state string) (string, error) {
	return "NotificationSent", nil
}

func TestAuditor(t *testing.T) {

	Convey("CommitScanner handler test", t, func() {
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
		auditorTestClients = &Clients{}
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
					Rules: []Rule{
						DummyRule{
							name:   "Dummy rule",
							result: &RuleResult{"Dummy rule", rulePassed, "", ""},
						},
					},
					notificationFunction: dummyNotifier,
				}},
			}
			escapedRepoURL := url.QueryEscape("https://dummy.googlesource.com/dummy.git/+/refs/heads/master")
			gitilesMockClient := gitilespb.NewMockGitilesClient(gomock.NewController(t))
			auditorTestClients.gitilesFactory = func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
				return gitilesMockClient, nil
			}
			Convey("Test scanning", func() {
				ds.Put(ctx, &RepoState{
					RepoURL:            "https://dummy.googlesource.com/dummy.git/+/refs/heads/master",
					ConfigName:         "dummy-repo",
					LastKnownCommit:    "123456",
					LastRelevantCommit: "999999",
				})

				Convey("No revisions", func() {
					gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
						Project:            "dummy",
						Committish:         "refs/heads/master",
						ExcludeAncestorsOf: "123456",
						PageSize:           6000,
					}).Return(&gitilespb.LogResponse{
						Log: []*git.Commit{},
					}, nil)
					resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
					So(err, ShouldBeNil)
					So(resp.StatusCode, ShouldEqual, 200)
					rs := &RepoState{RepoURL: "https://dummy.googlesource.com/dummy.git/+/refs/heads/master"}
					err = ds.Get(ctx, rs)
					So(err, ShouldBeNil)
					So(rs.LastKnownCommit, ShouldEqual, "123456")
					So(rs.LastRelevantCommit, ShouldEqual, "999999")
				})
				Convey("No interesting revisions", func() {
					gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
						Project:            "dummy",
						Committish:         "refs/heads/master",
						ExcludeAncestorsOf: "123456",
						PageSize:           6000,
					}).Return(&gitilespb.LogResponse{
						Log: []*git.Commit{{Id: "abcdef000123123"}},
					}, nil)
					resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
					So(err, ShouldBeNil)
					So(resp.StatusCode, ShouldEqual, 200)
					rs := &RepoState{RepoURL: "https://dummy.googlesource.com/dummy.git/+/refs/heads/master"}
					err = ds.Get(ctx, rs)
					So(err, ShouldBeNil)
					So(rs.LastKnownCommit, ShouldEqual, "abcdef000123123")
					So(rs.LastRelevantCommit, ShouldEqual, "999999")
				})
				Convey("Interesting revisions", func() {
					gitilesMockClient.EXPECT().Log(gomock.Any(), &gitilespb.LogRequest{
						Project:            "dummy",
						Committish:         "refs/heads/master",
						ExcludeAncestorsOf: "123456",
						PageSize:           6000,
					}).Return(&gitilespb.LogResponse{
						Log: []*git.Commit{
							{Id: "deadbeef"},
							{
								Id: "c001c0de",
								Author: &git.Commit_User{
									Email: "dummy@test.com",
									Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
								},
								Committer: &git.Commit_User{
									Email: "dummy@test.com",
									Time:  mustGitilesTime("Sun Sep 03 00:56:34 2017"),
								},
							},
						},
					}, nil)
					resp, err := client.Get(srv.URL + auditorPath + "?refUrl=" + escapedRepoURL)
					So(err, ShouldBeNil)
					So(resp.StatusCode, ShouldEqual, 200)
					rs := &RepoState{RepoURL: "https://dummy.googlesource.com/dummy.git/+/refs/heads/master"}
					err = ds.Get(ctx, rs)
					So(err, ShouldBeNil)
					So(rs.LastKnownCommit, ShouldEqual, "deadbeef")
					So(rs.LastRelevantCommit, ShouldEqual, "c001c0de")
					rc := &RelevantCommit{
						RepoStateKey: ds.KeyForObj(ctx, rs),
						CommitHash:   "c001c0de",
					}
					err = ds.Get(ctx, rc)
					So(err, ShouldBeNil)
					So(rc.PreviousRelevantCommit, ShouldEqual, "999999")
				})
			})
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
					Project:            "dummy",
					Committish:         "refs/heads/master",
					ExcludeAncestorsOf: "222222",
					PageSize:           6000,
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
						dummyRuleTmp := RuleMap["dummy-repo"].Rules["rules"].(AccountRules).Rules[0].(DummyRule)
						dummyRuleTmp.result.RuleResultStatus = ruleFailed
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
							So(rc.Status, ShouldEqual, auditCompletedWithActionRequired)
						}
					})
					Convey("Some panic", func() {
						RuleMap["dummy-repo"].Rules["rules"].(AccountRules).Rules[0] = panicRule{}
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
