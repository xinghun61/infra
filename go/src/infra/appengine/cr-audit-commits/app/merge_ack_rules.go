// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

// AcknowledgeMerge is a RuleFunc that acknowledges any merge into a release branch.
func AcknowledgeMerge(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{}
	result.RuleName = "AcknowledgeMerge"
	result.RuleResultStatus = ruleSkipped
	bugID, err := bugIDFromCommitMessage(rc.CommitMessage)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Found no bug on relevant commit %s", rc.CommitHash)
		return result
	}
	result.RuleResultStatus = notificationRequired
	result.MetaData, _ = SetToken(ctx, "BugNumbers", bugID, result.MetaData)
	return result
}
