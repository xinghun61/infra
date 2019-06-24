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
	typeDir  = "dir"
	typeFile = "file"
)

// OnlyModifiesFilesAndDirsRule is a shared implementation for Rules which
// verify that only the given files and directories are modified by the audited
// CL.
type OnlyModifiesFilesAndDirsRule struct {
	name  string
	files []string
	dirs  []string
}

// GetName returns the name of the rule, from the struct field 'name'.
func (rule OnlyModifiesFilesAndDirsRule) GetName() string {
	return rule.name
}

// Run executes the rule as configured by the struct fields 'files' and 'dirs'.
func (rule OnlyModifiesFilesAndDirsRule) Run(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	paths := make([]*Path, 0, len(rule.files)+len(rule.dirs))
	for _, f := range rule.files {
		paths = append(paths, &Path{
			Name: f,
			Type: typeFile,
		})
	}
	for _, d := range rule.dirs {
		paths = append(paths, &Path{
			Name: d,
			Type: typeDir,
		})
	}
	return OnlyModifiesPathsRuleImpl(ctx, ap, rc, cs, paths)
}

// Path is a struct describing a file or directory within the git repo.
type Path struct {
	Name string
	Type string
}

// OnlyModifiesPathsRuleImpl is a shared implementation for Rules which verify
// that only the given path(s) are modified by the audited CL.
func OnlyModifiesPathsRuleImpl(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, paths []*Path) *RuleResult {
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
		if p.Type == typeDir {
			name := p.Name
			if !strings.HasSuffix(name, "/") {
				name += "/"
			}
			dirs = append(dirs, name)
		} else if p.Type == typeFile {
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
