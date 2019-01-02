// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"flag"
	"io/ioutil"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCommaList(t *testing.T) {
	t.Parallel()
	Convey("Given a FlagSet with a CommaList flag", t, func() {
		fs := flag.NewFlagSet("test", flag.ContinueOnError)
		fs.Usage = func() {}
		fs.SetOutput(ioutil.Discard)
		var s []string
		fs.Var(NewCommaList(&s), "list", "Some list")
		Convey("When parsing with flag absent", func() {
			err := fs.Parse([]string{})
			Convey("The parsed slice should be empty", func() {
				So(err, ShouldEqual, nil)
				So(len(s), ShouldEqual, 0)
			})
		})
		Convey("When parsing a single item", func() {
			err := fs.Parse([]string{"-list", "foo"})
			Convey("The parsed slice should contain the item", func() {
				So(err, ShouldEqual, nil)
				So(s, ShouldResemble, []string{"foo"})
			})
		})
		Convey("When parsing multiple items", func() {
			err := fs.Parse([]string{"-list", "foo,bar,spam"})
			Convey("The parsed slice should contain the items", func() {
				So(err, ShouldEqual, nil)
				So(s, ShouldResemble, []string{"foo", "bar", "spam"})
			})
		})
	})
}
