// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

const (
	TYPE_DIR  = "dir"
	TYPE_FILE = "file"
)

// OnlyModifiesReleaseFiles is a RuleFunc that verifies that only
// release-related files are modified by the audited CL.
func OnlyModifiesReleaseFiles(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	files := []string{
		"chrome/MAJOR_BRANCH_DATE",
		"chrome/VERSION",
	}
	return OnlyModifiesFilesRule(ctx, ap, rc, cs, "OnlyModifiesReleaseFiles", files)
}

// OnlyModifiesFileRule is a shared implementation for RuleFuncs which verify
// that only one file is modified by the audited CL.
func OnlyModifiesFileRule(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, ruleName, file string) *RuleResult {
	return OnlyModifiesPathsRule(ctx, ap, rc, cs, ruleName, []*Path{
		&Path{
			Name: file,
			Type: TYPE_FILE,
		},
	})
}

// OnlyModifiesFilesRule is a shared implementation for RuleFuncs which verify
// that only the given files are modified by the audited CL.
func OnlyModifiesFilesRule(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, ruleName string, files []string) *RuleResult {
	paths := make([]*Path, 0, len(files))
	for _, f := range files {
		paths = append(paths, &Path{
			Name: f,
			Type: TYPE_FILE,
		})
	}
	return OnlyModifiesPathsRule(ctx, ap, rc, cs, ruleName, paths)
}

// OnlyModifiesDirRule is a shared implementation for RuleFuncs which verify
// that only files within the given directory are modified by the audited CL.
func OnlyModifiesDirRule(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, ruleName, dir string) *RuleResult {
	return OnlyModifiesPathsRule(ctx, ap, rc, cs, ruleName, []*Path{
		&Path{
			Name: dir,
			Type: TYPE_DIR,
		},
	})
}

// Path is a struct describing a file or directory within the git repo.
type Path struct {
	Name string
	Type string
}

// OnlyModifiesPathsRule is a shared implementation for RuleFuncs which verify
// that only the given path(s) are modified by the audited CL.
func OnlyModifiesPathsRule(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, ruleName string, paths []*Path) *RuleResult {
	// Find the diff.
	host, project, err := gitiles.ParseRepoURL(ap.RepoCfg.BaseRepoURL)
	if err != nil {
		panic(err)
	}
	gc, err := cs.NewGitilesClient(host)
	if err != nil {
		panic(err)
	}
	resp, err := gc.Log(ctx, &gitilespb.LogRequest{
		Project:    project,
		Committish: rc.CommitHash,
		PageSize:   1,
		TreeDiff:   true,
	})
	if err != nil {
		panic(err)
	}
	if len(resp.Log) != 1 {
		panic(fmt.Sprintf("Could not find commit %s through gitiles", rc.CommitHash))
	}
	td := resp.Log[0].TreeDiff

	// Verify that the CL only modifies the given paths.
	dirs := make([]string, 0, len(paths))
	files := make(map[string]bool, len(paths))
	for _, p := range paths {
		if p.Type == TYPE_DIR {
			name := p.Name
			if !strings.HasSuffix(name, "/") {
				name += "/"
			}
			dirs = append(dirs, name)
		} else if p.Type == TYPE_FILE {
			files[p.Name] = true
		}
	}
	check := func(path string) bool {
		if files[path] {
			return true
		}
		for _, dir := range dirs {
			if strings.HasPrefix(path, dir) {
				return true
			}
		}
		return false
	}
	ok := true
	for _, path := range td {
		if path.Type != git.Commit_TreeDiff_ADD && !check(path.OldPath) {
			ok = false
			break
		}
		if path.Type != git.Commit_TreeDiff_DELETE && !check(path.NewPath) {
			ok = false
			break
		}
	}

	// Report results.
	result := &RuleResult{
		RuleName:         ruleName,
		RuleResultStatus: ruleFailed,
	}
	if ok {
		result.RuleResultStatus = rulePassed
	} else {
		allowedPathsStr := ""
		if len(paths) > 0 {
			allowedPathsStr = paths[0].Name
			for _, p := range paths[1:] {
				allowedPathsStr += ", " + p.Name
			}
		}
		result.Message = fmt.Sprintf("The automated account %s was expected to only modify one of [%s] on the automated commit %s"+
			" but it seems to have modified other files.", ap.TriggeringAccount, allowedPathsStr, rc.CommitHash)
	}
	return result
}
