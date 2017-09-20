// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"bufio"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/cr-audit-commits/buildstatus"
	buildbot "infra/monitoring/messages"
	"infra/monorail"
)

const (
	// TODO(robertocn): Move this to the gitiles library.
	gerritScope       = "https://www.googleapis.com/auth/gerritcodereview"
	emailScope        = "https://www.googleapis.com/auth/userinfo.email"
	failedBuildPrefix = "Sample Failed Build:"
)

// Tests can put mock clients here, prod code will ignore this global.
var testClients *Clients

type gerritClientInterface interface {
	GetChangeDetails(context.Context, string, []string) (*gerrit.Change, error)
	ChangeQuery(context.Context, gerrit.ChangeQueryRequest) ([]*gerrit.Change, bool, error)
}

type gitilesClientInterface interface {
	LogForward(context.Context, string, string, string) ([]gitiles.Commit, error)
	Log(context.Context, string, string, int) ([]gitiles.Commit, error)
}

type miloClientInterface interface {
	GetBuildInfo(context.Context, string) (*buildbot.Build, error)
}

// getGitilesClient creates a new gitiles client bound to a new http client
// that is bound to an authenticated transport.
func getGitilesClient(ctx context.Context) (*gitiles.Client, error) {
	httpClient, err := getAuthenticatedHTTPClient(ctx, gerritScope, emailScope)
	if err != nil {
		return nil, err
	}
	return &gitiles.Client{Client: httpClient}, nil
}

// TODO(robertocn): move this into a dedicated file for authentication, and
// accept a list of scopes to make this function usable for communicating for
// different systems.
func getAuthenticatedHTTPClient(ctx context.Context, scopes ...string) (*http.Client, error) {
	var t http.RoundTripper
	var err error
	if len(scopes) > 0 {
		t, err = auth.GetRPCTransport(ctx, auth.AsSelf, auth.WithScopes(scopes...))
	} else {
		t, err = auth.GetRPCTransport(ctx, auth.AsSelf)
	}

	if err != nil {
		return nil, err
	}

	return &http.Client{Transport: t}, nil
}

func failedBuildFromCommitMessage(m string) (string, error) {
	s := bufio.NewScanner(strings.NewReader(m))
	for s.Scan() {
		line := s.Text()
		if strings.HasPrefix(line, failedBuildPrefix) {
			return strings.TrimSpace(strings.TrimPrefix(line, failedBuildPrefix)), nil
		}
	}
	return "", fmt.Errorf("commit message does not contain url to failed build prefixed with %q", failedBuildPrefix)
}

func getIssueBySummaryAndAccount(ctx context.Context, cfg *RepoConfig, s, a string, cs *Clients) (*monorail.Issue, error) {
	q := fmt.Sprintf("summary:\"%s\" reporter:\"%s\"", s, a)
	req := &monorail.IssuesListRequest{
		ProjectId: cfg.MonorailProject,
		Can:       monorail.IssuesListRequest_ALL,
		Q:         q,
	}
	resp, err := cs.monorail.IssuesList(ctx, req)
	if err != nil {
		return nil, err
	}
	for _, iss := range resp.Items {
		if iss.Summary == s {
			return iss, nil
		}
	}
	return nil, nil
}

func postComment(ctx context.Context, cfg *RepoConfig, i *monorail.Issue, c string, cs *Clients) error {
	req := &monorail.InsertCommentRequest{
		Comment: &monorail.InsertCommentRequest_Comment{
			Content: c,
		},
		Issue: &monorail.IssueRef{
			IssueId:   i.Id,
			ProjectId: cfg.MonorailProject,
		},
	}
	_, err := cs.monorail.InsertComment(ctx, req)
	return err
}

func postIssue(ctx context.Context, cfg *RepoConfig, s, d string, cs *Clients) (int32, error) {
	iss := &monorail.Issue{
		Description: d,
		Components:  []string{cfg.MonorailComponent},
		Labels:      cfg.MonorailLabels,
		Status:      monorail.StatusUntriaged,
		Summary:     s,
	}

	req := &monorail.InsertIssueRequest{
		ProjectId: cfg.MonorailProject,
		Issue:     iss,
		SendEmail: true,
	}

	resp, err := cs.monorail.InsertIssue(ctx, req)
	if err != nil {
		return 0, err
	}
	return resp.Issue.Id, nil
}

func issueFromID(ctx context.Context, cfg *RepoConfig, ID int32, cs *Clients) (*monorail.Issue, error) {
	req := &monorail.IssuesListRequest{
		ProjectId: cfg.MonorailProject,
		Can:       monorail.IssuesListRequest_ALL,
		Q:         strconv.Itoa(int(ID)),
	}
	resp, err := cs.monorail.IssuesList(ctx, req)
	if err != nil {
		return nil, err
	}
	for _, iss := range resp.Items {
		if iss.Id == ID {
			return iss, nil
		}
	}
	return nil, fmt.Errorf("could not find an issue with ID %d", ID)
}

func resultText(cfg *RepoConfig, rc *RelevantCommit, issueExists bool) string {
	sort.Slice(rc.Result, func(i, j int) bool {
		if rc.Result[i].RuleResultStatus == rc.Result[j].RuleResultStatus {
			return rc.Result[i].RuleName < rc.Result[j].RuleName
		}
		return rc.Result[i].RuleResultStatus < rc.Result[j].RuleResultStatus
	})
	rows := []string{}
	for _, rr := range rc.Result {
		rows = append(rows, fmt.Sprintf(" - %s: %s -- %s", rr.RuleName, rr.RuleResultStatus.ToString(), rr.Message))
	}

	results := fmt.Sprintf("Here's a summary of the rules that were executed: \n%s",
		strings.Join(rows, "\n"))

	if issueExists {
		return results
	}

	description := "An audit of the git repository at %q found at least one violation when auditing" +
		" commit %s created by %s and committed by %s.\n\n%s"

	return fmt.Sprintf(description, cfg.RepoURL(), rc.CommitHash, rc.AuthorAccount, rc.CommitterAccount, results)

}

func getFailedBuild(ctx context.Context, miloClient miloClientInterface, rc *RelevantCommit) (string, *buildbot.Build) {
	buildURL, err := failedBuildFromCommitMessage(rc.CommitMessage)
	if err != nil {
		return "", nil
	}

	failedBuildInfo, err := miloClient.GetBuildInfo(ctx, buildURL)
	if err != nil {
		panic(err)
	}
	return buildURL, failedBuildInfo
}

// Clients exposes clients for external services shared throughout one request.
type Clients struct {

	// Instead of actual clients, use interfaces so that tests
	// can inject mock clients as needed.
	gerrit  gerritClientInterface
	gitiles gitilesClientInterface
	milo    miloClientInterface

	// This is already an interface so we use it as exported.
	monorail monorail.MonorailClient
}

// ConnectAll creates the clients so the rules can use them.
func (c *Clients) ConnectAll(ctx context.Context, cfg *RepoConfig) error {
	var err error
	c.gitiles, err = getGitilesClient(ctx)
	if err != nil {
		return err
	}

	httpClient, err := getAuthenticatedHTTPClient(ctx, gerritScope, emailScope)
	if err != nil {
		return err
	}
	c.gerrit, err = gerrit.NewClient(httpClient, cfg.GerritURL)
	if err != nil {
		return err
	}

	c.milo, err = buildstatus.NewAuditMiloClient(ctx, auth.AsSelf)
	if err != nil {
		return err
	}

	c.monorail = monorail.NewEndpointsClient(httpClient, cfg.MonorailAPIURL)
	return nil
}

func loadConfig(rc *router.Context) (*RepoConfig, string, error) {
	ctx, req := rc.Context, rc.Request
	repo := req.FormValue("repo")
	cfg, hasConfig := RuleMap[repo]
	if !hasConfig {
		logging.Errorf(ctx, "No audit rules defined for %s", repo)
		return nil, "", fmt.Errorf("No audit rules defined for %s", repo)
	}

	return cfg, repo, nil
}

func initializeClients(ctx context.Context, cfg *RepoConfig) (*Clients, error) {
	if testClients != nil {
		return testClients, nil
	}
	cs := &Clients{}
	err := cs.ConnectAll(ctx, cfg)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not create external clients")
		return nil, fmt.Errorf("Could not create external clients")
	}
	return cs, nil
}
