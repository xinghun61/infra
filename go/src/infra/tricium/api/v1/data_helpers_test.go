// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetPathForDataType(t *testing.T) {
	Convey("Test Environment", t, func() {

		Convey("Known data type has path", func() {
			d := &Data_GitFileDetails{}
			_, err := GetPathForDataType(d)
			So(err, ShouldBeNil)
		})

		Convey("Unknown data type returns an error", func() {
			_, err := GetPathForDataType("jkgdsjf")
			So(err, ShouldNotBeNil)
		})
	})
}
