// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMonorail(t *testing.T) {
	t.Parallel()

	Convey("Monorail", t, func() {
		Convey("IssueURL", func() {
			expected := "https://bugs.chromium.org/p/chromium/issues/detail?id=123"
			actual := IssueURL("bugs.chromium.org", "chromium", 123)
			So(actual, ShouldEqual, expected)
		})
	})
}
