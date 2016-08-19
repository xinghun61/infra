// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCommon(t *testing.T) {
	t.Parallel()

	Convey("Number", t, func() {
		Convey("UnmarshalJSON", func() {
			Convey("fails on non integers", func() {
				Convey("string", func() {
					input := []byte("foo")
					var num Number
					So(json.Unmarshal(input, &num), ShouldNotBeNil)
				})

				Convey("float", func() {
					input := []byte("2.0")
					var num Number
					So(json.Unmarshal(input, &num), ShouldNotBeNil)
				})
			})

			Convey("succeeds for integer", func() {
				input := []byte("-400")
				var num Number
				So(json.Unmarshal(input, &num), ShouldBeNil)
				So(num, ShouldEqual, -400)
			})
		})

		Convey("MarshalJSON", func() {
			Convey("basic", func() {
				num := Number(-400)
				b, err := json.Marshal(&num)
				So(err, ShouldBeNil)
				So(string(b), ShouldEqual, "-400")
			})
		})
	})
}
