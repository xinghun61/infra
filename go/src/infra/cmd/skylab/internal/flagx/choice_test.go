// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"flag"
	"io/ioutil"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestChoice(t *testing.T) {
	t.Parallel()
	Convey("Given a FlagSet with a Choice flag", t, func() {
		fs := flag.NewFlagSet("test", flag.ContinueOnError)
		fs.Usage = func() {}
		fs.SetOutput(ioutil.Discard)
		var s string
		fs.Var(NewChoice(&s, "Apple", "Orange"), "fruit", "")
		Convey("When parsing with flag absent", func() {
			err := fs.Parse([]string{})
			Convey("The parsed string should be empty", func() {
				So(err, ShouldBeNil)
				So(s, ShouldEqual, "")
			})
		})
		Convey("When parsing a valid choice", func() {
			err := fs.Parse([]string{"-fruit", "Orange"})
			Convey("The parsed flag equals that choice", func() {
				So(err, ShouldBeNil)
				So(s, ShouldEqual, "Orange")
			})
		})
		Convey("When parsing an invalid choice", func() {
			err := fs.Parse([]string{"-fruit", "Onion"})
			Convey("An error is returned", func() {
				So(err, ShouldNotBeNil)
				So(s, ShouldEqual, "")
			})
		})
	})
}
