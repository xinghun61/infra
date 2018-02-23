// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crauditcommits

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRulesConfig(t *testing.T) {
	t.Parallel()
	Convey("Ensure RuleMap keys are valid", t, func() {
		for k := range RuleMap {
			So(k, ShouldNotEqual, "AuditFailure")
		}
	})
}
