// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestExtractAnalyzerPlatform(t *testing.T) {
	Convey("Test Environment", t, func() {
		analyzerName := "Lint"
		platform := "UBUNTU"
		a, p, err := ExtractAnalyzerPlatform(analyzerName + workerSeparator + platform)
		So(err, ShouldBeNil)
		So(a, ShouldEqual, analyzerName)
		So(p, ShouldEqual, platform)
		_, _, err = ExtractAnalyzerPlatform(analyzerName)
		So(err, ShouldNotBeNil)
	})
}
