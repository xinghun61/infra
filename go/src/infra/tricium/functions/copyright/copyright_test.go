// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"infra/tricium/api/v1"
)

func TestCheckMissingCopyright(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Correct BSD copyright", func() {
			path := "test/src/good.cpp"
			So(checkCopyright(path), ShouldBeNil)
		})
		Convey("Correct MIT copyright", func() {
			path := "test/src/good_mit.cpp"
			So(checkCopyright(path), ShouldBeNil)
		})
		Convey("Incorrect copyright", func() {
			path := "test/src/bad.cpp"
			c := checkCopyright(path)
			So(c, ShouldNotBeNil)
			So(c, ShouldResemble, &tricium.Data_Comment{
				Category:  "Copyright/Incorrect",
				Message:   "Incorrect copyright statement.\nUse the following for BSD:\nCopyright <year> The <group> Authors. All rights reserved.\nUse of this source code is governed by a BSD-style license that can be\nfound in the LICENSE file.\n\nOr the following for MIT: Copyright <year> The <group> Authors\n\nUse of this source code is governed by a MIT-style\nlicense that can be found in the LICENSE file or at\nhttps://opensource.org/licenses/MIT",
				Path:      path,
				StartLine: 1,
				EndLine:   1,
				StartChar: 0,
				EndChar:   1,
				Url:       "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
			})
		})
		Convey("Missing copyright", func() {
			path := "test/src/missing.cpp"
			c := checkCopyright(path)
			So(c, ShouldNotBeNil)
			So(c, ShouldResemble, &tricium.Data_Comment{
				Category:  "Copyright/Missing",
				Message:   "Missing copyright statement.\nUse the following for BSD:\nCopyright <year> The <group> Authors. All rights reserved.\nUse of this source code is governed by a BSD-style license that can be\nfound in the LICENSE file.\n\nOr the following for MIT: Copyright <year> The <group> Authors\n\nUse of this source code is governed by a MIT-style\nlicense that can be found in the LICENSE file or at\nhttps://opensource.org/licenses/MIT",
				Path:      path,
				StartLine: 1,
				EndLine:   1,
				StartChar: 0,
				EndChar:   1,
				Url:       "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
			})
		})
	})

	Convey("Out-of-date copyright", t, func() {
		path := "test/src/old.cpp"
		c := checkCopyright(path)
		So(c, ShouldNotBeNil)
		So(c, ShouldResemble, &tricium.Data_Comment{
			Category:  "Copyright/OutOfDate",
			Message:   "Out of date copyright statement (omit the (c) to update)",
			Path:      path,
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   1,
			Url:       "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
		})
	})
}
