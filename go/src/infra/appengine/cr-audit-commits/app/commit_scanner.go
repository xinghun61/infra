// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/ptypes"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"
)

// CommitScanner is a handler function that gets the list of new commits and
// if they are eithered authored or committed by an account defined in RuleMap
// (see rules.go), records details about them and schedules detailed audits.
//
// It expects the 'repo' parameter containing the name of a configured repo
// e.g. "chromium-src-master"
//
// The handler uses this url as a key to retrieve the state of the last run
// from the datastore and resume the git log from the last known commit.
//
// Returns 200 http status if no errors occur.
func CommitScanner(rc *router.Context) {
	// TODO(crbug.com/806108): Refactor these handlers to return errors if
	// appropriate and handle them in a wrapper that logs errors and gives
	// the corresponding http status code.
	ctx, resp, req := rc.Context, rc.Writer, rc.Request
	repo := req.FormValue("repo")
	rev := ""
	// Supported repositories are those present as keys in RuleMap.
	// see rules_config.go.
	cfg, hasConfig := RuleMap[repo]
	if !hasConfig {
		http.Error(resp, fmt.Sprintf("No audit rules defined for %s", repo), 400)
		return
	}
	repoState := &RepoState{RepoURL: cfg.RepoURL()}
	switch err := ds.Get(ctx, repoState); err {
	case ds.ErrNoSuchEntity:
		// This is the first time the scanner runs, use the hard-coded
		// starting commit.
		rev = cfg.StartingCommit
		repoState = &RepoState{
			RepoURL:         cfg.RepoURL(),
			LastKnownCommit: rev,
		}
	case nil:
		rev = repoState.LastKnownCommit
		if rev == "" {
			rev = cfg.StartingCommit
		}
		if rev == "" {
			http.Error(resp, fmt.Sprintf("The specified repository %s is missing a starting revision", repo), 400)
			return
		}
	default:
		http.Error(resp, err.Error(), 500)
		return
	}

	cs, err := initializeClients(ctx, cfg)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	host, project, err := gitiles.ParseRepoURL(cfg.BaseRepoURL)
	if err != nil {
		http.Error(resp, err.Error(), 500)
		return
	}

	logReq := gitilespb.LogRequest{
		Project:  project,
		Ancestor: rev,
		Treeish:  cfg.BranchName,
	}

	gc, err := cs.NewGitilesClient(host)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not create new gitiles client")
		http.Error(resp, err.Error(), 500)
		return
	}
	fl, err := gitiles.PagingLog(ctx, gc, logReq, 6000)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not get gitiles log from revision %s", rev)
		http.Error(resp, err.Error(), 500)
		return
	}
	// Reverse the log to get revisions after `rev` time-ascending order.
	for i, j := 0, len(fl)-1; i < j; i, j = i+1, j-1 {
		fl[i], fl[j] = fl[j], fl[i]
	}

	// Make sure the log reaches the last known commit.
	if len(fl) > 0 && rev != "" && len(fl[0].Parents) > 0 && fl[0].Parents[0] != rev {
		panic("There is a gap between the last known commit and the beginning of the forward log")

	}
	// TODO(robertocn): Make sure that we break out of this for loop if we
	// reach a deadline of ~5 mins (Since cron job have a 10 minute
	// deadline). Use the context for this.
	for _, commit := range fl {
		relevant := false
		for _, ruleSet := range cfg.Rules {
			if ruleSet.MatchesCommit(commit) {
				n, err := saveNewRelevantCommit(ctx, repoState, commit)
				if err != nil {
					logging.WithError(err).Errorf(ctx, "Could not save new relevant commit")
					http.Error(resp, err.Error(), 500)
					return
				}
				repoState.LastRelevantCommit = n.CommitHash
				repoState.LastRelevantCommitTime = n.CommitTime
				// If the commit matches one ruleSet that's
				// enough. Break to move on to the next commit.
				relevant = true
				break
			}
		}
		ScannedCommits.Add(ctx, 1, relevant, repo)
		repoState.LastKnownCommit = commit.Id
		// Ignore possible error, this time is used for display purposes only.
		if commit.Committer != nil {
			ct, _ := ptypes.Timestamp(commit.Committer.Time)
			repoState.LastKnownCommitTime = ct
		}
	}
	// If this Put or the one in saveNewRelevantCommit fail, we risk
	// auditing the same commit twice.
	if err := ds.Put(ctx, repoState); err != nil {
		logging.WithError(err).Errorf(ctx, "Could not save last known/interesting commits")
		http.Error(resp, err.Error(), 500)
		return
	}
}

func saveNewRelevantCommit(ctx context.Context, state *RepoState, commit *git.Commit) (*RelevantCommit, error) {
	rk := ds.KeyForObj(ctx, state)

	commitTime, err := ptypes.Timestamp(commit.GetCommitter().GetTime())
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Invalid commit time: %s", commitTime)
		return nil, err
	}
	rc := &RelevantCommit{
		RepoStateKey:           rk,
		CommitHash:             commit.Id,
		PreviousRelevantCommit: state.LastRelevantCommit,
		Status:                 auditScheduled,
		CommitTime:             commitTime,
		CommitterAccount:       commit.Committer.Email,
		AuthorAccount:          commit.Author.Email,
		CommitMessage:          commit.Message,
	}

	if err := ds.Put(ctx, rc, state); err != nil {
		logging.WithError(err).Errorf(ctx, "Could not save %s", rc.CommitHash)
		return nil, err
	}
	logging.Infof(ctx, "saved %s", rc)

	return rc, nil
}
