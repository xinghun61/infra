// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"errors"
	"fmt"
	"testing"
	"time"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
)

func TestFinditRules(t *testing.T) {
	t.Parallel()

	Convey("Initialize configuration", t, func() {
		ctx := memory.Use(context.Background())
		datastore.GetTestable(ctx).CatchupIndexes()
		// Mock gerrit query, details (inner map)
		// Mock gitiles log
		// Create relevantCommit
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:     datastore.KeyForObj(ctx, rs),
			CommitHash:       "12ebe127",
			Status:           auditScheduled,
			CommitTime:       time.Date(2017, time.August, 25, 15, 0, 0, 0, time.UTC),
			CommitterAccount: "findit@sample.com",
			AuthorAccount:    "findit@sample.com",
			CommitMessage:    "Fake revert",
		}
		cfg := &RepoConfig{
			State:       rs,
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "master",
		}
		ap := &AuditParams{
			TriggeringAccount: "findit@sample.com",
			RepoCfg:           cfg,
		}
		rvc := &gerrit.Change{
			ChangeID: "revertcid",
			RevertOf: 666,
		}
		cc := &gerrit.Change{
			ChangeID:        "culpritcid",
			ChangeNumber:    666,
			CurrentRevision: "badc0de",
		}
		q := map[string][]*gerrit.Change{
			"12ebe127":  {rvc},
			"revertcid": {rvc},
			"666":       {cc},
		}
		cfg.gerritClient = &mockGerritClient{q: q}

		// Create ap{repoconfig{mockclients...}}
		// Test pass.
		Convey("Culprit age Pass", func() {
			// Inject gitiles log response
			r := []gitiles.Commit{
				{
					Commit: "badc0de",
					Committer: gitiles.User{
						Time: "Fri Aug 25 07:00:00 2017",
					},
				},
			}
			cfg.gitilesClient = &mockGitilesClient{r: r}
			// Run rule
			rr := CulpritAge(ctx, ap, rc)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)

		})
		Convey("Culprit age Fail", func() {
			// Inject gitiles log response
			r := []gitiles.Commit{
				{
					Commit: "badc0de",
					Committer: gitiles.User{
						Time: "Fri Aug 18 07:00:00 2017",
					},
				},
			}
			cfg.gitilesClient = &mockGitilesClient{r: r}
			// Run rule
			rr := CulpritAge(ctx, ap, rc)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)

		})
		Convey("Culprit age Error", func() {
			// Inject gitiles error
			cfg.gitilesClient = &mockGitilesClient{e: errors.New("Some error")}
			// Run rule
			rr := func() {
				CulpritAge(ctx, ap, rc)
			}
			// Check result code
			So(rr, ShouldPanic)
		})
		Convey("Auto-reverts per day Pass", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoRevertsPerDay, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "cq@other.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoRevertsPerDay(ctx, ap, rcs[0])
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Auto-reverts per day Failed", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoRevertsPerDay+1, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "cq@other.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoRevertsPerDay(ctx, ap, rcs[0])
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, fmt.Sprintf("%d commits were created", MaxAutoRevertsPerDay+1))
		})
		Convey("Auto-commits per day Pass", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoCommitsPerDay, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "findit@sample.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoCommitsPerDay(ctx, ap, rcs[0])
			So(rr.RuleResultStatus, ShouldEqual, rulePassed)
		})
		Convey("Auto-commits per day Failed", func() {
			k := datastore.KeyForObj(ctx, rs)
			d := time.Duration(-1) * time.Hour
			t := time.Now().UTC()
			rcs := fakeRelevantCommits(MaxAutoCommitsPerDay+1, k, "7e57c100", auditCompleted, t, d, "findit@sample.com", "findit@sample.com")
			err := datastore.Put(ctx, rcs)
			So(err, ShouldBeNil)
			rr := AutoCommitsPerDay(ctx, ap, rcs[0])
			So(rr.RuleResultStatus, ShouldEqual, ruleFailed)
			So(rr.Message, ShouldContainSubstring, fmt.Sprintf("%d commits were committed", MaxAutoCommitsPerDay+1))
		})
	})
}
