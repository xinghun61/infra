// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func TestStatusPage(t *testing.T) {
	Convey("Test Status Page", t, func() {
		ctx := memory.Use(context.Background())

		statusPath := "/admin/status"

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			ds.GetTestable(ctx).CatchupIndexes()
			next(c)
		}
		templatesmw := router.NewMiddlewareChain(withTestingContext).Extend(
			templates.WithTemplates(&templates.Bundle{
				Loader:  templates.FileSystemLoader("templates"),
				FuncMap: templateFuncs,
			}))

		r := router.New()
		r.GET(statusPath, templatesmw, Status)
		srv := httptest.NewServer(r)
		client := &http.Client{}
		Convey("Invalid Repo", func() {
			resp, err := client.Get(srv.URL + statusPath + "?refUrl=unknown")
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldContainSubstring, "Unknown repository")
			So(resp.StatusCode, ShouldEqual, 200)
		})
		Convey("Valid Repo", func() {
			RuleMap["new-repo"] = &RepoConfig{
				BaseRepoURL:    "https://new.googlesource.com/new.git",
				GerritURL:      "https://new-review.googlesource.com",
				BranchName:     "master",
				StartingCommit: "000000",
				Rules: map[string]RuleSet{"rules": AccountRules{
					Account: "new@test.com",
					Rules: []Rule{
						DummyRule{
							name:   "DummyRule",
							result: &RuleResult{"Dummy rule", rulePassed, "", ""},
						},
					},
				}},
			}
			Convey("No interesting revisions", func() {
				rs := &RepoState{
					RepoURL:            "https://new.googlesource.com/new.git/+/master",
					LastRelevantCommit: "",
					LastKnownCommit:    "000000",
					ConfigName:         "new-repo",
				}
				err := ds.Put(ctx, rs)
				So(err, ShouldBeNil)
				resp, err := client.Get(srv.URL + statusPath + "?refUrl=" + url.QueryEscape(
					"https://new.googlesource.com/new.git/+/master"))
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, 200)
				// There is a link to the last scanned rev
				b, err := ioutil.ReadAll(resp.Body)
				resp.Body.Close()
				linkText := fmt.Sprintf("%s/+/000000", RuleMap["new-repo"].BaseRepoURL)
				So(string(b), ShouldContainSubstring, linkText)
			})
			Convey("Some interesting revisions", func() {
				rs := &RepoState{
					RepoURL:            "https://new.googlesource.com/new.git/+/master",
					LastRelevantCommit: "111111",
					LastKnownCommit:    "121212",
					ConfigName:         "new-repo",
				}
				err := ds.Put(ctx, rs)
				So(err, ShouldBeNil)
				rsk := ds.KeyForObj(ctx, rs)

				for i := 0; i < 12; i++ {
					cTime, _ := time.Parse("2006-01-02T15:04", fmt.Sprintf("2017-09-01T09:%02d", i+1))
					relevantCommit := &RelevantCommit{
						RepoStateKey: rsk,
						CommitHash:   fmt.Sprintf("%02d%02d%02d", i, i, i),
						Status:       AuditStatus(i % 3), // Alternate all statuses.
						Result: []RuleResult{
							{"First Rule", rulePassed, "", ""},
							{"Second Rule", ruleFailed, "Some rules fail", ""},
							{"Third Rule", ruleSkipped, "Some rules are skipped", ""},
						},
						CommitTime: cTime,
					}
					if i > 0 {
						relevantCommit.PreviousRelevantCommit = fmt.Sprintf("%02d%02d%02d", i-1, i-1, i-1)
					}
					So(ds.Put(ctx, relevantCommit), ShouldBeNil)
				}
				resp, err := client.Get(srv.URL + statusPath + "?refUrl=" + url.QueryEscape(
					"https://new.googlesource.com/new.git/+/master") + "&n=11")
				So(err, ShouldBeNil)
				defer resp.Body.Close()
				b, err := ioutil.ReadAll(resp.Body)
				So(resp.StatusCode, ShouldEqual, 200)
				for i := 1; i < 12; i++ {
					linkText := fmt.Sprintf("%s/+/%02d%02d%02d", RuleMap["new-repo"].BaseRepoURL, i, i, i)
					So(string(b), ShouldContainSubstring, linkText)
				}
			})
		})
		srv.Close()
	})
}
