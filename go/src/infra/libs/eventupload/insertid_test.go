// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package eventupload

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGenerate(t *testing.T) {
	t.Parallel()

	prefix := "testPrefix"
	id := InsertIDGenerator{}
	id.Prefix = prefix

	Convey("Test InsertIDGenerator increments counter with calls to Generate", t, func() {
		Convey("Test InsertIDGenerator increments counter with calls to Generate", func() {
			for i := 1; i < 10; i++ {
				want := fmt.Sprintf("%s:%d", prefix, i)
				Convey(fmt.Sprintf("When Generate is called %d time(s), the value of the counter is correct", i), func() {
					got := id.Generate()
					So(got, ShouldEqual, want)
				})
			}
		})
	})
}
