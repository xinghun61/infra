// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package bbutil

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBBUtil(t *testing.T) {
	t.Parallel()

	Convey("BBUtil", t, func() {
		So(
			BuildSetURL("patch/rietveld/codereview.chromium.org/2841003002/1"),
			ShouldEqual,
			"https://codereview.chromium.org/2841003002/#ps1",
		)
		So(
			BuildSetURL("patch/gerrit/chromium-review.googlesource.com/1/2"),
			ShouldEqual,
			"https://chromium-review.googlesource.com/c/1/2",
		)
		So(BuildSetURL("trash"), ShouldEqual, "")
	})
}
