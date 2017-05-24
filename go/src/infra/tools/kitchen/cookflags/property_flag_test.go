// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cookflags

import (
	"flag"
	"testing"

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

func TestPropertyFlag(t *testing.T) {
	t.Parallel()

	Convey("PropertyFlag", t, func() {
		fs := flag.NewFlagSet("test", flag.ContinueOnError)
		fs.Usage = func() {}
		f := PropertyFlag{}
		fs.Var(&f, "prop", "use the flag")

		Convey("works", func() {
			So(fs.Parse([]string{"-prop", `{"stuff": "yes"}`}), ShouldBeNil)

			So(f, ShouldResemble, PropertyFlag{
				"stuff": "yes",
			})

			So(f.String(), ShouldResemble, `{"stuff":"yes"}`)
		})

		Convey("breaks appropriately", func() {
			So(fs.Parse([]string{"-prop", `wat`}), ShouldErrLike,
				"invalid character 'w'")
			So(fs.Parse([]string{"-prop", `{"stuff": "yes"} extra crap`}), ShouldErrLike,
				"invalid character 'e' after top-level value")
		})
	})
}
