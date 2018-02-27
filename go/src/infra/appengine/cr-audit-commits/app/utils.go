// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"bufio"
	"fmt"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/logging"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
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
	failedStepPrefix  = "Sample Failed Step:"
	bugIDRegex        = "^(?i)Bug(:|=)(.*)"
)

// Tests can put mock clients here, prod code will ignore this global.
var testClients *Clients

type gerritClientInterface interface {
	ChangeDetails(context.Context, string, gerrit.ChangeDetailsParams) (*gerrit.Change, error)
	ChangeQuery(context.Context, gerrit.ChangeQueryParams) ([]*gerrit.Change, bool, error)
	IsChangePureRevert(context.Context, string) (bool, error)
}

type miloClientInterface interface {
	GetBuildInfo(context.Context, string) (*buildbot.Build, error)
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

func findPrefixLine(m string, prefix string) (string, error) {
	s := bufio.NewScanner(strings.NewReader(m))
	for s.Scan() {
		line := s.Text()
		if strings.HasPrefix(line, prefix) {
			return strings.TrimSpace(strings.TrimPrefix(line, prefix)), nil
		}
	}
	return "", fmt.Errorf("commit message does not contain line prefixed with %q", prefix)
}
func failedBuildFromCommitMessage(m string) (string, error) {
	return findPrefixLine(m, failedBuildPrefix)
}

func failedStepFromCommitMessage(m string) (string, error) {
	return findPrefixLine(m, failedStepPrefix)
}

func bugIDFromCommitMessage(m string) (string, error) {
	s := bufio.NewScanner(strings.NewReader(m))
	for s.Scan() {
		line := s.Text()
		re := regexp.MustCompile(bugIDRegex)
		matches := re.FindAllStringSubmatch(line, -1)
		if len(matches) != 0 {
			for _, m := range matches {
				return strings.Replace(string(m[2]), " ", "", -1), nil
			}
		}
	}
	return "", fmt.Errorf("commit message does not contain any bug id")
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

func postComment(ctx context.Context, cfg *RepoConfig, iID int32, c string, cs *Clients) error {
	req := &monorail.InsertCommentRequest{
		Comment: &monorail.InsertCommentRequest_Comment{
			Content: c,
		},
		Issue: &monorail.IssueRef{
			IssueId:   iID,
			ProjectId: cfg.MonorailProject,
		},
	}
	_, err := cs.monorail.InsertComment(ctx, req)
	return err
}

func postIssue(ctx context.Context, cfg *RepoConfig, s, d string, cs *Clients, components, labels []string) (int32, error) {
	// The components for the issue will be the additional components
	// depending on which rules were violated, and the component defined
	// for the repo(if any).
	iss := &monorail.Issue{
		Description: d,
		Components:  components,
		Labels:      labels,
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

	description := "An audit of the git commit at %q found at least one violation. \n" +
		" The commit was created by %s and committed by %s.\n\n%s"

	return fmt.Sprintf(description, cfg.LinkToCommit(rc.CommitHash), rc.AuthorAccount, rc.CommitterAccount, results)

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
	gerrit gerritClientInterface
	milo   miloClientInterface

	httpClient *http.Client

	// This is already an interface so we use it as exported.
	monorail       monorail.MonorailClient
	gitilesFactory GitilesClientFactory
}

// GitilesClientFactory is function type for generating new gitiles clients,
// both the production client factory and any mock factories are expected to
// implement it.
type GitilesClientFactory func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error)

// ProdGitilesClientFactory is a GitilesClientFactory used to create production
// gitiles REST clients.
func ProdGitilesClientFactory(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
	gc, err := gitiles.NewRESTClient(httpClient, host, true)
	if err != nil {
		return nil, err
	}
	return gc, nil
}

// NewGitilesClient uses a factory set in the Clients object and its httpClient
// to create a new gitiles client.
func (c *Clients) NewGitilesClient(host string) (gitilespb.GitilesClient, error) {
	gc, err := c.gitilesFactory(host, c.httpClient)
	if err != nil {
		return nil, err
	}
	return gc, nil
}

// ConnectAll creates the clients so the rules can use them, also sets
// necessary values in the context for the clients to talk to production.
func (c *Clients) ConnectAll(ctx context.Context, cfg *RepoConfig) error {
	var err error
	c.httpClient, err = getAuthenticatedHTTPClient(ctx, gerritScope, emailScope)
	if err != nil {
		return err
	}

	c.gerrit, err = gerrit.NewClient(c.httpClient, cfg.GerritURL)
	if err != nil {
		return err
	}

	c.milo, err = buildstatus.NewAuditMiloClient(ctx, auth.AsSelf)
	if err != nil {
		return err
	}

	c.monorail = monorail.NewEndpointsClient(c.httpClient, cfg.MonorailAPIURL)
	c.gitilesFactory = ProdGitilesClientFactory
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
