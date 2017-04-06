// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

// TestDefaultGitRetryRegexps test expected strings against the resulting regexp
// to ensure that they match.
func TestDefaultGitRetryRegexps(t *testing.T) {
	t.Parallel()

	Convey(`Default Git retry regexps match expected lines`, t, func() {
		for _, line := range []string{
			`!   [remote rejected] (error in hook) $TRAILING_CONTENT`,
			`!   [remote rejected] (failed to lock) $TRAILING_CONTENT`,
			`!   [remote rejected] (error in Gerrit backend) $TRAILING_CONTENT`,
			`remote error: Internal Server Error`,
			`fatal: Couldn't find remote ref $TRAILING_CONTENT`,
			`git fetch_pack: expected ACK/NAK, got $TRAILING_CONTENT`,
			`protocol error: bad pack header`,
			`The remote end hung up unexpectedly`,
			`TLS packet with unexpected length was received`,
			`RPC failed; result=12345, HTTP code = 500`,
			`Connection timed out`,
			`repository cannot accept new pushes; contact support`,
			`Service Temporarily Unavailable`,
			`Connection refused`,
			`connection refused`, // Ignore case.
			`The requested URL returned error: 598`,
			`Connection reset by peer`,
			`Unable to look up $TRAILING_CONTENT`,
			`Couldn't resolve host`,
			`Unknown SSL protocol error in connection to foo.example.com:443`,
		} {
			Convey(fmt.Sprintf(`Matches line: %q`, line), func() {
				So(DefaultGitRetryRegexp.MatchString(line), ShouldBeTrue)
			})
		}
	})
}
