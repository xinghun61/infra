// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCheckSpaceMix(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Tab and single space", func() {
			path := "test.file"
			line := "\t some code"
			pos := 1
			c := checkSpaceMix(path, line, pos)
			So(c, ShouldNotBeNil)
			So(c.StartLine, ShouldEqual, pos)
			So(c.EndLine, ShouldEqual, pos)
			So(c.StartChar, ShouldEqual, 0)
			So(c.EndChar, ShouldEqual, 1)
		})
		Convey("Tab and multiple space", func() {
			path := "test.file"
			line := "\t  some code"
			pos := 1
			c := checkSpaceMix(path, line, pos)
			So(c, ShouldNotBeNil)
			So(c.StartLine, ShouldEqual, pos)
			So(c.EndLine, ShouldEqual, pos)
			So(c.StartChar, ShouldEqual, 0)
			So(c.EndChar, ShouldEqual, 2)
		})
	})
}

func TestCheckTrailingSpace(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Single trailing spaces", func() {
			path := "test.file"
			line := "some code "
			pos := 1
			c := checkTrailingSpace(path, line, pos)
			So(c, ShouldNotBeNil)
			So(c.StartLine, ShouldEqual, pos)
			So(c.EndLine, ShouldEqual, pos)
			So(c.StartChar, ShouldEqual, len(line)-1)
			So(c.EndChar, ShouldEqual, len(line)-1)
		})
		Convey("Multiple trailing spaces", func() {
			path := "test.file"
			line := "some code  "
			pos := 1
			c := checkTrailingSpace(path, line, pos)
			So(c, ShouldNotBeNil)
			So(c.StartLine, ShouldEqual, pos)
			So(c.EndLine, ShouldEqual, pos)
			So(c.StartChar, ShouldEqual, len(line)-2)
			So(c.EndChar, ShouldEqual, len(line)-1)
		})
	})

}
