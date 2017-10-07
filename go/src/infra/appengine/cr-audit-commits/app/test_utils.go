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

	"google.golang.org/grpc"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"

	buildbot "infra/monitoring/messages"
	mr "infra/monorail"
)

type mockGitilesClient struct {
	r []gitiles.Commit
	e error
}

func (c mockGitilesClient) LogForward(ctx context.Context, baseURL, rev, branch string, opts ...gitiles.LogOption) ([]gitiles.Commit, error) {
	return c.r, c.e
}

func (c mockGitilesClient) Log(ctx context.Context, baseURL, treeish string, opts ...gitiles.LogOption) ([]gitiles.Commit, error) {
	return c.r, c.e
}

type mockGerritClient struct {
	q  map[string][]*gerrit.Change
	pr map[string]bool
	e  error
}

func (c mockGerritClient) ChangeQuery(ctx context.Context, r gerrit.ChangeQueryRequest) ([]*gerrit.Change, bool, error) {
	ret := c.q[r.Query]
	return ret, false, c.e
}

func (c mockGerritClient) GetChangeDetails(ctx context.Context, cid string, options []string) (*gerrit.Change, error) {
	ret := c.q[cid]
	return ret[0], c.e
}

func (c mockGerritClient) IsChangePureRevert(ctx context.Context, cid string) (bool, error) {
	// Say a revert is a pure revert if present in c.pr, and its value is
	// true.
	val, ok := c.pr[cid]
	return ok && val, c.e
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

type mockMiloClient struct {
	q map[string]*buildbot.Build
	e error
}

func (c mockMiloClient) GetBuildInfo(ctx context.Context, URL string) (*buildbot.Build, error) {
	return c.q[URL], c.e
}

type mockMonorailClient struct {
	il *mr.IssuesListResponse
	ic *mr.InsertCommentResponse
	ii *mr.InsertIssueResponse
	e  error
}

func (c mockMonorailClient) InsertIssue(ctx context.Context, in *mr.InsertIssueRequest, opts ...grpc.CallOption) (*mr.InsertIssueResponse, error) {
	return c.ii, c.e
}

func (c mockMonorailClient) InsertComment(ctx context.Context, in *mr.InsertCommentRequest, opts ...grpc.CallOption) (*mr.InsertCommentResponse, error) {
	return c.ic, c.e
}

func (c mockMonorailClient) IssuesList(ctx context.Context, in *mr.IssuesListRequest, opts ...grpc.CallOption) (*mr.IssuesListResponse, error) {
	return c.il, c.e
}
