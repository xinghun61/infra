// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"strconv"
	"time"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
)

type mockGitilesClient struct {
	r []gitiles.Commit
	e error
}

func (c mockGitilesClient) LogForward(ctx context.Context, baseURL, rev, branch string) ([]gitiles.Commit, error) {
	return c.r, c.e
}

func (c mockGitilesClient) Log(ctx context.Context, baseURL, treeish string, limit int) ([]gitiles.Commit, error) {
	return c.r, c.e
}

type mockGerritClient struct {
	q map[string][]*gerrit.Change
	e error
}

func (c mockGerritClient) ChangeQuery(ctx context.Context, r gerrit.ChangeQueryRequest) ([]*gerrit.Change, bool, error) {
	ret := c.q[r.Query]
	return ret, false, c.e
}

func (c mockGerritClient) GetChangeDetails(ctx context.Context, cid string, options []string) (*gerrit.Change, error) {
	ret := c.q[cid]
	return ret[0], c.e
}

func fakeRelevantCommits(n int, k *ds.Key, bh string, s AuditStatus, t time.Time, d time.Duration, a, c string) []*RelevantCommit {
	result := []*RelevantCommit{}
	for i := 0; i < n; i++ {
		prevHash := bh + strconv.Itoa(i+1)
		if i == n-1 {
			prevHash = ""
		}
		result = append(result, &RelevantCommit{
			RepoStateKey:           k,
			CommitHash:             bh + strconv.Itoa(i),
			Status:                 s,
			CommitTime:             t,
			CommitterAccount:       c,
			AuthorAccount:          a,
			CommitMessage:          fmt.Sprintf("Fake commit %d", i),
			PreviousRelevantCommit: prevHash,
		})
		t = t.Add(d)
	}
	return result
}
