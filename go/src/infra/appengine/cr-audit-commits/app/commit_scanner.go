// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/logging"
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
	ctx, resp, req := rc.Context, rc.Writer, rc.Request
	repo := req.FormValue("repo")
	rev := ""
	// Supported repositories are those present as keys in RuleMap.
	// see rules_config.go.
	repoConfig, hasConfig := RuleMap[repo]
	if !hasConfig {
		http.Error(resp, fmt.Sprintf("No audit rules defined for %s", repo), 400)
		return
	}
	repoConfig.State = &RepoState{RepoURL: repoConfig.RepoURL()}
	switch err := ds.Get(ctx, repoConfig.State); err {
	case ds.ErrNoSuchEntity:
		// This is the first time the scanner runs, use the hard-coded
		// starting commit.
		rev = repoConfig.StartingCommit
		repoConfig.State = &RepoState{
			RepoURL:         repoConfig.RepoURL(),
			LastKnownCommit: rev,
		}
	case nil:
		rev = repoConfig.State.LastKnownCommit
		if rev == "" {
			rev = repoConfig.StartingCommit
		}
		if rev == "" {
			http.Error(resp, fmt.Sprintf("The specified repository %s is missing a starting revision", repo), 400)
			return
		}
	default:
		http.Error(resp, err.Error(), 500)
		return
	}
	var cs *Clients
	if testClients != nil {
		cs = testClients
	} else {
		cs = &Clients{}
		err := cs.ConnectAll(ctx, repoConfig)
		if err != nil {
			logging.WithError(err).Errorf(ctx, "Could not create external clients")
			http.Error(resp, err.Error(), 500)
			return
		}
	}
	fl, err := cs.gitiles.LogForward(ctx, repoConfig.BaseRepoURL, rev, repoConfig.BranchName)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not get gitiles log from revision %s", rev)
		http.Error(resp, err.Error(), 500)
		return
	}
	// TODO(robertocn): Make sure that we break out of this for loop if we
	// reach a deadline of ~5 mins (Since cron job have a 10 minute
	// deadline). Use the context for this.
	for _, commit := range fl {
		for _, ruleSet := range repoConfig.Rules {
			if ruleSet.MatchesCommit(commit) {
				n, err := saveNewRelevantCommit(ctx, repoConfig.State, commit)
				if err != nil {
					logging.WithError(err).Errorf(ctx, "Could not save new relevant commit")
					http.Error(resp, err.Error(), 500)
					return
				}
				repoConfig.State.LastRelevantCommit = n.CommitHash
				// If the commit matches one ruleSet that's
				// enough. Break to move on to the next commit.
				break
			}
		}
		repoConfig.State.LastKnownCommit = commit.Commit
	}
	// If this Put or the one in saveNewRelevantCommit fail, we risk
	// auditing the same commit twice.
	if err := ds.Put(ctx, repoConfig.State); err != nil {
		logging.WithError(err).Errorf(ctx, "Could not save last known/interesting commits")
		http.Error(resp, err.Error(), 500)
		return
	}
}

func saveNewRelevantCommit(ctx context.Context, state *RepoState, commit gitiles.Commit) (*RelevantCommit, error) {
	rk := ds.KeyForObj(ctx, state)

	commitTime, err := commit.Committer.GetTime()
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not get commit time from commit")
		return nil, err
	}
	rc := &RelevantCommit{
		RepoStateKey:           rk,
		CommitHash:             commit.Commit,
		PreviousRelevantCommit: state.LastRelevantCommit,
		Status:                 auditScheduled,
		CommitTime:             commitTime,
		CommitterAccount:       commit.Committer.Email,
		AuthorAccount:          commit.Author.Email,
		CommitMessage:          commit.Message,
	}

	if err := ds.Put(ctx, rc, state); err != nil {
		logging.WithError(err).Errorf(ctx, "Could not save %s", rc)
		return nil, err
	}
	logging.Infof(ctx, "saved %s", rc)

	return rc, nil
}
