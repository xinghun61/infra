// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package migration

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestMigration(t *testing.T) {
	t.Parallel()

	Convey("transformProperties", t, func() {
		expectedMasters := map[string]string{
			"linux_chromium_rel_ng":     "tryserver.chromium.linux",
			"mac_chromium_rel_ng":       "tryserver.chromium.mac",
			"win_chromium_rel_ng":       "tryserver.chromium.win",
			"mac_angle_rel_ng":          "tryserver.chromium.angle",
			"android_unswarmed_n5x_rel": "tryserver.chromium.android",
			"cast_shell_android":        "tryserver.chromium.android",
			"linux_android_dbg_ng":      "tryserver.chromium.android",
		}
		for builder, expectedMaster := range expectedMasters {
			builder := builder
			expectedMaster := expectedMaster
			Convey("works for "+builder, func() {
				props := map[string]interface{}{
					"mastername":  "luci.chromium.try",
					"buildername": "LUCI " + builder,
					"foo":         "bar",
				}
				So(TransformProperties(props), ShouldBeNil)
				So(props["mastername"], ShouldEqual, expectedMaster)
				So(props["buildername"], ShouldEqual, builder)
				So(props["foo"], ShouldEqual, "bar")
			})
		}
		Convey("noop if no master", func() {
			props := map[string]interface{}{
				"buildername": "linux_chromium_rel_ng",
			}
			So(TransformProperties(props), ShouldBeNil)
			So(props["buildername"], ShouldEqual, "linux_chromium_rel_ng")
		})
		Convey("noop if builder does not start with LUCI", func() {
			props := map[string]interface{}{
				"mastername":  "luci.chromium.try",
				"buildername": "linux_chromium_rel_ng",
			}
			So(TransformProperties(props), ShouldBeNil)
			So(props["mastername"], ShouldEqual, "tryserver.chromium.linux")
			So(props["buildername"], ShouldEqual, "linux_chromium_rel_ng")
		})
		Convey("noop if master isn't known", func() {
			props := map[string]interface{}{
				"mastername":  "luci.fuchsia.try",
				"buildername": "linux_chromium_rel_ng",
			}
			So(TransformProperties(props), ShouldBeNil)
			So(props["mastername"], ShouldEqual, "luci.fuchsia.try")
			So(props["buildername"], ShouldEqual, "linux_chromium_rel_ng")
		})
		Convey("fails if buildername is not present", func() {
			props := map[string]interface{}{
				"mastername": "luci.chromium.try",
				"foo":        "bar",
			}
			So(TransformProperties(props), ShouldErrLike, "buildername property is not set")
		})
	})
}
