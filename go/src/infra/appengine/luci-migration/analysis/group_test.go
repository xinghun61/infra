// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analysis

import (
	"testing"

	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func side(duration time.Duration, results ...string) groupSide {
	s := make(groupSide, len(results))
	for i, r := range results {
		s[i] = build("dummy", duration, r)
	}
	return s
}

func TestGroup(t *testing.T) {
	t.Parallel()

	Convey("Group", t, func() {
		Convey("success", func() {
			So(side(time.Hour, success).success(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeFalse)
		})
		Convey("trustworthy", func() {
			So(side(time.Hour, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeFalse)
		})
	})
}
