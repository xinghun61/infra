// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package masters

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMasters(t *testing.T) {
	t.Parallel()

	Convey("Masters", t, func() {
		Convey("Known Masters", func() {
			Convey("ByName", func() {
				Convey("existing", func() {
					So(ByName("TryServerChromiumMac"), ShouldResemble, &Master{
						Name:       "TryServerChromiumMac",
						Identifier: "tryserver.chromium.mac",
					})
				})

				Convey("not existing", func() {
					So(ByName("FooBar"), ShouldBeNil)
					So(ByName("tryserver.chromium.mac"), ShouldBeNil)
				})
			})

			Convey("ByIdentifier", func() {
				Convey("existing", func() {
					So(ByIdentifier("tryserver.chromium.linux"), ShouldResemble, &Master{
						Name:       "TryServerChromiumLinux",
						Identifier: "tryserver.chromium.linux",
					})
				})

				Convey("not existing", func() {
					So(ByIdentifier("foo.bar"), ShouldBeNil)
					So(ByIdentifier("TryServerChromiumLinux"), ShouldBeNil)
				})
			})
		})
	})
}
