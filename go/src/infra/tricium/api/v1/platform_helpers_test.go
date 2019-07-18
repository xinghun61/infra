// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetPlatforms(t *testing.T) {

	Convey("PlatformBitPosToMask", t, func() {
		So(PlatformBitPosToMask(0), ShouldEqual, 0)
		So(PlatformBitPosToMask(1), ShouldEqual, 1)
		So(PlatformBitPosToMask(2), ShouldEqual, 2)
		So(PlatformBitPosToMask(3), ShouldEqual, 4)
		So(PlatformBitPosToMask(4), ShouldEqual, 8)
		So(PlatformBitPosToMask(5), ShouldEqual, 16)
	})

	Convey("Platform: ANY", t, func() {
		values, err := GetPlatforms(PlatformBitPosToMask(Platform_ANY))
		So(err, ShouldBeNil)
		So(values, ShouldResemble, []Platform_Name{Platform_ANY})
	})

	Convey("Platform: UBUNTU", t, func() {
		values, err := GetPlatforms(PlatformBitPosToMask(Platform_UBUNTU))
		So(err, ShouldBeNil)
		So(values, ShouldResemble, []Platform_Name{Platform_UBUNTU})
	})

	Convey("Platform: ANDROID|OSX|WINDOWS", t, func() {
		values, err := GetPlatforms(
			PlatformBitPosToMask(Platform_ANDROID) +
				PlatformBitPosToMask(Platform_OSX) +
				PlatformBitPosToMask(Platform_WINDOWS))
		So(err, ShouldBeNil)
		So(values, ShouldResemble, []Platform_Name{
			Platform_ANDROID,
			Platform_OSX,
			Platform_WINDOWS,
		})
	})

	Convey("Platform: Invalid", t, func() {
		// Position 60 is unused.
		values, err := GetPlatforms(PlatformBitPosToMask(60))
		So(err, ShouldNotBeNil)
		So(values, ShouldBeNil)
	})
}
