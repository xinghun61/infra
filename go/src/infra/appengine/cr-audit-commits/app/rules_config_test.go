// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/proto/git"
)

func TestRulesConfig(t *testing.T) {
	t.Parallel()
	Convey("Ensure RuleMap keys are valid", t, func() {
		for k := range RuleMap {
			So(k, ShouldNotEqual, "AuditFailure")
		}
	})
	Convey("AccountRules", t, func() {
		commit := &git.Commit{
			Author:    &git.Commit_User{Email: "dummy1@test1.com"},
			Committer: &git.Commit_User{Email: "dummy2@test2.com"},
		}
		So(AccountRules{Account: "dummy1@test1.com"}.MatchesCommit(commit), ShouldBeTrue)
		So(AccountRules{Account: "dummy2@test2.com"}.MatchesCommit(commit), ShouldBeTrue)
		So(AccountRules{Account: "dummy3@test3.com"}.MatchesCommit(commit), ShouldBeFalse)
		So(AccountRules{Account: "*"}.MatchesCommit(commit), ShouldBeTrue)
	})
}
