// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestExtractFunctionPlatform(t *testing.T) {
	Convey("Test Environment", t, func() {
		functionName := "Lint"
		platform := "UBUNTU"
		f, p, err := ExtractFunctionPlatform(functionName + workerSeparator + platform)
		So(err, ShouldBeNil)
		So(f, ShouldEqual, functionName)
		So(p, ShouldEqual, platform)
		_, _, err = ExtractFunctionPlatform(functionName)
		So(err, ShouldNotBeNil)
	})
}
