// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetPathForDataType(t *testing.T) {
	Convey("Known data type has path", t, func() {
		d := &Data_GitFileDetails{}
		_, err := GetPathForDataType(d)
		So(err, ShouldBeNil)
	})

	Convey("Unknown data type returns an error", t, func() {
		_, err := GetPathForDataType("jkgdsjf")
		So(err, ShouldNotBeNil)
	})
}

func TestFilterFiles(t *testing.T) {

	Convey("Filter with an empty list of patterns", t, func() {
		// The result is the union of all files that match any of the
		// patterns, so if no patterns are given, then the result is
		// empty.
		files := []*Data_File{{Path: "x/y/z.py"}, {Path: "x/y/z.txt"}}
		filtered, err := FilterFiles(files)
		So(err, ShouldBeNil)
		So(filtered, ShouldBeEmpty)
	})

	Convey("Filter with one pattern", t, func() {
		// Note that the pattern only has to match the basename.
		files := []*Data_File{{Path: "x/y/z.py"}, {Path: "x/y/z.txt"}}
		filtered, err := FilterFiles(files, "*.py")
		So(err, ShouldBeNil)
		So(filtered, ShouldResemble, []*Data_File{{Path: "x/y/z.py"}})
	})

	Convey("Filter with one invalid pattern", t, func() {
		files := []*Data_File{{Path: "x/y/z.py"}, {Path: "x/y/z.txt"}}
		_, err := FilterFiles(files, "[-]")
		So(err, ShouldNotBeNil)
	})

	Convey("Filter with two patterns", t, func() {
		files := []*Data_File{{Path: "x/y/z.py"}, {Path: "x/y/z.txt"}}
		filtered, err := FilterFiles(files, "*.py", "*.txt")
		So(err, ShouldBeNil)
		So(filtered, ShouldResemble, files)
	})

	Convey("Filter with two patterns that overlap", t, func() {
		files := []*Data_File{{Path: "x/y/z.py"}, {Path: "x/y/z.txt"}}
		filtered, err := FilterFiles(files, "*", "*.txt")
		So(err, ShouldBeNil)
		So(filtered, ShouldResemble, files)
	})
}
