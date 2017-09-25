// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"
	"strconv"

	"golang.org/x/net/context"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

// Status displays recent information regarding the audit app's activity on
// the monitored repositories.
func Status(rctx *router.Context) {
	ctx, req, resp := rctx.Context, rctx.Request, rctx.Writer
	repoName := req.FormValue("repo")
	if repoName == "" {
		repoName = "chromium-src-master"
	}

	cfg, hasConfig := RuleMap[repoName]
	if !hasConfig {
		args := templates.Args{
			"RuleMap": RuleMap,
			"Error":   fmt.Sprintf("Unknown repository %s", repoName),
		}
		templates.MustRender(ctx, resp, "pages/status.html", args)
		return
	}
	repoState := &RepoState{RepoURL: cfg.RepoURL()}
	err := ds.Get(ctx, repoState)
	if err != nil {
		handleError(ctx, err, repoName, cfg, repoState, resp)
		return
	}

	nCommits := 10
	n := req.FormValue("n")
	if n != "" {
		nCommits, err = strconv.Atoi(n)
		if err != nil {
			// We are swallowing the error on purpose,
			// rather than fail, use default.
			nCommits = 10
		}
	}
	commits := []*RelevantCommit{}
	if repoState.LastRelevantCommit != "" {
		rc := &RelevantCommit{
			CommitHash:   repoState.LastRelevantCommit,
			RepoStateKey: ds.KeyForObj(ctx, repoState),
		}

		err = ds.Get(ctx, rc)
		if err != nil {
			handleError(ctx, err, repoName, cfg, repoState, resp)
			return
		}

		commits, err = lastXRelevantCommits(ctx, rc, nCommits)
		if err != nil {
			handleError(ctx, err, repoName, cfg, repoState, resp)
			return
		}
	}
	args := templates.Args{
		"Commits":          commits,
		"LastRelevant":     repoState.LastRelevantCommit,
		"LastRelevantTime": repoState.LastRelevantCommitTime,
		"LastScanned":      repoState.LastKnownCommit,
		"LastScannedTime":  repoState.LastKnownCommitTime,
		"RepoName":         repoName,
		"RepoConfig":       cfg,
		"RuleMap":          RuleMap,
	}
	templates.MustRender(ctx, resp, "pages/status.html", args)
}

func handleError(ctx context.Context, err error, repoName string, cfg *RepoConfig, repoState *RepoState, resp http.ResponseWriter) {
	logging.WithError(err).Errorf(ctx, "Getting status of repo %s(%s), for revision %s", repoName, cfg.RepoURL(), repoState.LastRelevantCommit)
	http.Error(resp, "Getting status failed. See log for details.", 500)
}

func lastXRelevantCommits(ctx context.Context, rc *RelevantCommit, x int) ([]*RelevantCommit, error) {
	current := rc
	result := []*RelevantCommit{rc}
	for counter := 1; counter < x; counter++ {
		if current.PreviousRelevantCommit == "" {
			break
		}

		current = &RelevantCommit{
			CommitHash:   current.PreviousRelevantCommit,
			RepoStateKey: rc.RepoStateKey,
		}
		err := ds.Get(ctx, current)
		if err != nil {
			return nil, err
		}
		result = append(result, current)
	}
	return result, nil
}
