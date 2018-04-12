// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"fmt"

	"golang.org/x/net/context"
)

// OnlyModifiesDEPSFile is a RuleFunc that verifies that the only file
// modified by the audited CL is ``DEPS``.
func OnlyModifiesDEPSFile(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) *RuleResult {
	result := &RuleResult{
		Message: fmt.Sprintf("The automated account %s was expected to only modify %s on the automated commit %s"+
			" but it seems to have modified other files.", ap.TriggeringAccount, "DEPS", rc.CommitHash),
	}
	result.RuleName = "OnlyModifiesDEPSFile"
	result.RuleResultStatus = ruleFailed

	ok, err := onlyModifies(ctx, ap, rc, cs, "DEPS")
	if err != nil {
		panic(err)
	}
	if ok {
		result.RuleResultStatus = rulePassed
	}
	return result
}
