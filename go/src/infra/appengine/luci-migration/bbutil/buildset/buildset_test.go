// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildset

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBBUtil(t *testing.T) {
	t.Parallel()

	Convey("BuildSet", t, func() {
		So(
			Parse("patch/rietveld/codereview.chromium.org/2841003002/1").URL(),
			ShouldEqual,
			"https://codereview.chromium.org/2841003002/#ps1",
		)
		So(
			Parse("patch/gerrit/chromium-review.googlesource.com/1/2").URL(),
			ShouldEqual,
			"https://chromium-review.googlesource.com/c/1/2",
		)
		So(Parse("trash").URL(), ShouldEqual, "")
	})
}
