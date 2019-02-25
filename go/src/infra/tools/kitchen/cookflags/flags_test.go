// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cookflags

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

var flagTestCases = []struct {
	flags       []string
	cf          CookFlags
	errParse    interface{}
	errValidate interface{}
}{
	{
		flags:       []string{},
		errValidate: "-checkout-dir doesn't exist",
	},

	{
		flags: []string{
			"-checkout-dir", ".",
			"-recipe", "yep",
			"-properties", `{"some": "thing"}`, "-properties-file", "bar",
		},
		errValidate: "only one of -properties or -properties-file",
	},

	{
		flags: []string{
			"-checkout-dir", ".",
			"-recipe", "cool_recipe",
			"-call-update-build",
		},
		errValidate: `-call-update-build requires -buildbucket-hostname`,
	},
	{
		flags: []string{
			"-checkout-dir", ".",
			"-recipe", "cool_recipe",
			"-buildbucket-hostname", "buildbucket.example.com",
			"-call-update-build",
		},
		errValidate: `-call-update-build requires a valid -buildbucket-build-id`,
	},
}

func TestFlags(t *testing.T) {
	t.Parallel()

	cwd, err := os.Getwd()
	if err != nil {
		panic(err)
	}
	r := strings.NewReplacer(
		cwd, "$CWD",
		"\\", "/",
	)

	Convey("Flags", t, func() {
		cf := CookFlags{}
		fs := flag.NewFlagSet("test_flags", flag.ContinueOnError)
		fs.Usage = func() {}

		Convey("can register them", func() {
			cf.Register(fs)

			Convey("and parse some flags", func() {
				for _, tc := range flagTestCases {
					Convey(fmt.Sprintf("%v", tc.flags), func() {
						So(fs.Parse(tc.flags), ShouldErrLike, tc.errParse)
						if tc.errParse == nil {
							if tc.errValidate == nil {
								So(cf.Dump(), ShouldResemble, tc.flags)
								data, err := json.Marshal(cf)
								So(err, ShouldBeNil)
								cf2 := &CookFlags{}
								So(json.Unmarshal(data, cf2), ShouldBeNil)
								So(&cf, ShouldResemble, cf2)
							}
							So(cf.Normalize(), ShouldErrLike, tc.errValidate)
							if tc.errValidate == nil {
								cf.TempDir = r.Replace(cf.TempDir)
								So(cf, ShouldResemble, tc.cf)
							}
						}
					})
				}
			})
		})
	})
}
