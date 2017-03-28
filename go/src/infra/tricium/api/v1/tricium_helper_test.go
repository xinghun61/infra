// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestIsDone(t *testing.T) {
	Convey("Test Environment", t, func() {

		Convey("Done means done", func() {
			done := IsDone(State_SUCCESS)
			So(done, ShouldBeTrue)
			done = IsDone(State_FAILURE)
			So(done, ShouldBeTrue)
		})

		Convey("Pending or running is not done", func() {
			done := IsDone(State_PENDING)
			So(done, ShouldBeFalse)
			done = IsDone(State_RUNNING)
			So(done, ShouldBeFalse)
		})
	})
}
