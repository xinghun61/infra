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
}

func TestCheckTrailingSpace(t *testing.T) {
	Convey("Test Environment", t, func() {
		path := "test.file"
		line := "some code  "
		pos := 1
		c := checkTrailingSpace(path, line, pos)
		So(c, ShouldNotBeNil)
		So(c.StartLine, ShouldEqual, pos)
		So(c.EndLine, ShouldEqual, pos)
		So(c.StartChar, ShouldEqual, 9)
		So(c.EndChar, ShouldEqual, 10)
	})

}
