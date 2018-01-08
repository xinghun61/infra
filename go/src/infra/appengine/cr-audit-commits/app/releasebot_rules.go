// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gitiles"
)

// OnlyModifiesVersionFile is a RuleFunc that verifies that the only filed
// modified by the audited CL is ``chrome/VERSION``.
func OnlyModifiesVersionFile(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "OnlyModifiesVersionFile"
	result.RuleResultStatus = ruleFailed

	ok, err := onlyModifies(ctx, ap, rc, cs, "chrome/VERSION")
	if err != nil {
		panic(err)
	}
	if ok {
		result.RuleResultStatus = rulePassed
	}
	return result
}

func onlyModifies(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients, fn string) (bool, error) {
	c, err := cs.gitiles.Log(ctx, ap.RepoCfg.BaseRepoURL, rc.CommitHash, gitiles.Limit(1))
	if err != nil {
		return false, err
	}
	if len(c) != 1 {
		return false, fmt.Errorf("Could not find commit %s through gitiles", rc.CommitHash)
	}
	td := c[0].TreeDiff
	return len(td) == 1 && strings.ToLower(td[0].Type) == "modify" && td[0].OldPath == fn && td[0].NewPath == fn, nil
}
