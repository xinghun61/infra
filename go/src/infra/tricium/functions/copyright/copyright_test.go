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
		Convey("Correct copyright", func() {
			path := "test/src/good.cpp"
			So(checkCopyright(path), ShouldBeNil)
		})
		Convey("Incorrect copyright", func() {
			path := "test/src/bad.cpp"
			c := checkCopyright(path)
			So(c, ShouldNotBeNil)
			So(c, ShouldResemble, &tricium.Data_Comment{
				Category: "Copyright/Incorrect",
				Message:  "Incorrect copyright statement",
				Path:     path,
				Url:      "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
			})
		})
		Convey("Missing copyright", func() {
			path := "test/src/missing.cpp"
			c := checkCopyright(path)
			So(c, ShouldNotBeNil)
			So(c, ShouldResemble, &tricium.Data_Comment{
				Category: "Copyright/Missing",
				Message:  "Missing copyright statement",
				Path:     path,
				Url:      "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
			})
		})
		Convey("Out-of-date copyright", func() {
			path := "test/src/old.cpp"
			c := checkCopyright(path)
			So(c, ShouldNotBeNil)
			So(c, ShouldResemble, &tricium.Data_Comment{
				Category: "Copyright/OutOfDate",
				Message:  "Out of date copyright statement (omit the (c) to update)",
				Path:     path,
				Url:      "https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
			})
		})
	})
}
