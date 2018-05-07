// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"infra/tricium/api/v1"
)

func TestCheckSpaceMix(t *testing.T) {
	Convey("Finds tab + single space mix", t, func() {
		So(checkSpaceMix("test.file", "\t code", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   1,
		})
	})

	Convey("Finds tab + multiple space mix", t, func() {
		So(checkSpaceMix("test.file", "\t  code", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   2,
		})
	})

	Convey("Finds space + tab mix", t, func() {
		So(checkSpaceMix("test.file", " \tcode", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   1,
		})
	})

	Convey("Finds other whitespace mix", t, func() {
		So(checkSpaceMix("test.file", "\t\v\f...", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   2,
		})
	})

	Convey("Produces no comment for mid-line space mix", t, func() {
		So(checkSpaceMix("test.file", "+ \tcode", 1), ShouldBeNil)
	})

	Convey("Produces no comment in Makefile", t, func() {
		So(checkSpaceMix("Makefile", "\t  some code", 1), ShouldBeNil)
	})

	Convey("Produces no comment in makefile with extension", t, func() {
		So(checkSpaceMix("my.mk", "\t  some code", 1), ShouldBeNil)
	})

	Convey("Produces no comment in patch file", t, func() {
		So(checkSpaceMix("my.patch", " \t\tsome code", 1), ShouldBeNil)
	})
}

func TestCheckTrailingSpace(t *testing.T) {
	Convey("Finds single trailing space", t, func() {
		So(checkTrailingSpace("test.file", "code ", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/TrailingSpace",
			Message:   "Found trailing space",
			StartLine: 1,
			EndLine:   1,
			StartChar: 4,
			EndChar:   4,
		})
	})

	Convey("Finds multiple trailing spaces", t, func() {
		So(checkTrailingSpace("test.file", "code  ", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/TrailingSpace",
			Message:   "Found trailing space",
			StartLine: 1,
			EndLine:   1,
			StartChar: 4,
			EndChar:   5,
		})
	})

	Convey("Produces no comment in patch file", t, func() {
		So(checkTrailingSpace("my.patch", " ", 1), ShouldBeNil)
	})
}
