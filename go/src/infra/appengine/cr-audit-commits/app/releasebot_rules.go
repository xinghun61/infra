// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/proto/git"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
)

// OnlyModifiesVersionFile is a RuleFunc that verifies that the only filed
// modified by the audited CL is ``chrome/VERSION``.
func OnlyModifiesVersionFile(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{
		RuleName:         "OnlyModifiesVersionFile",
		RuleResultStatus: ruleFailed,
	}

	ok, err := onlyModifies(ctx, ap, rc, cs, "chrome/VERSION")
	if err != nil {
		panic(err)
	}
	if ok {
		result.RuleResultStatus = rulePassed
		result.Message = ""
	} else {
		result.RuleResultStatus = ruleFailed
		result.Message = fmt.Sprintf("The automated account %s was expected to only modify %s on the automated commit %s"+
			" but it seems to have modified other files.", ap.TriggeringAccount, "chrome/VERSION", rc.CommitHash)
	}
	return result
}

func onlyModifies(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, fn string) (bool, error) {
	host, project, err := gitiles.ParseRepoURL(ap.RepoCfg.BaseRepoURL)
	if err != nil {
		return false, err
	}
	gc, err := cs.NewGitilesClient(host)
	if err != nil {
		return false, err
	}
	resp, err := gc.Log(ctx, &gitilespb.LogRequest{
		Project:  project,
		Treeish:  rc.CommitHash,
		PageSize: 1,
		TreeDiff: true,
	})
	if err != nil {
		return false, err
	}
	if len(resp.Log) != 1 {
		return false, fmt.Errorf("Could not find commit %s through gitiles", rc.CommitHash)
	}
	td := resp.Log[0].TreeDiff
	return len(td) == 1 && td[0].Type == git.Commit_TreeDiff_MODIFY && td[0].OldPath == fn && td[0].NewPath == fn, nil
}
