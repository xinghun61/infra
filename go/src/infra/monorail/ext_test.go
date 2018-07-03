// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestExt(t *testing.T) {
	t.Parallel()

	Convey("FindCC", t, func() {
		issue := &Issue{
			Cc: []*AtomPerson{{Name: "a"}, {Name: "b"}},
		}
		b := issue.FindCC("b")
		So(b, ShouldNotBeNil)
		So(b.Name, ShouldEqual, "b")

		c := issue.FindCC("c")
		So(c, ShouldBeNil)
	})
}
