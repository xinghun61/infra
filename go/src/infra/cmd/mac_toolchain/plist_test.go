// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPlistReading(t *testing.T) {
	t.Parallel()

	Convey("getXcodeVersion works", t, func() {
		Convey("for valid plist", func() {
			xv, bv, err := getXcodeVersion("testdata/version.plist")
			So(err, ShouldBeNil)
			So(xv, ShouldEqual, "TESTXCODEVERSION")
			So(bv, ShouldEqual, "TESTBUILDVERSION")
		})
		Convey("when version is missing", func() {
			_, _, err := getXcodeVersion("testdata/badKeys.plist")
			So(err, ShouldNotBeNil)
		})
		Convey("when version file is broken", func() {
			_, _, err := getXcodeVersion("testdata/broken.plist")
			So(err, ShouldNotBeNil)
		})
		Convey("when version file is missing", func() {
			_, _, err := getXcodeVersion("testdata/nonexistent")
			So(err, ShouldNotBeNil)
		})
	})

	Convey("getXcodeLicenseInfo works", t, func() {
		Convey("for valid plist", func() {
			lid, lt, err := getXcodeLicenseInfo("testdata/licenseInfoGood.plist")
			So(err, ShouldBeNil)
			So(lid, ShouldEqual, "TESTID")
			So(lt, ShouldEqual, "Beta")
		})
		Convey("when license keys are missing", func() {
			_, _, err := getXcodeLicenseInfo("testdata/badKeys.plist")
			So(err, ShouldNotBeNil)
		})
		Convey("when license file is broken", func() {
			_, _, err := getXcodeLicenseInfo("testdata/broken.plist")
			So(err, ShouldNotBeNil)
		})
		Convey("when license file is missing", func() {
			_, _, err := getXcodeLicenseInfo("testdata/nonexistent")
			So(err, ShouldNotBeNil)
		})
	})
}
