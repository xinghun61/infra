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

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

var flagTestCases = []struct {
	flags       []string
	cf          CookFlags
	errParse    interface{}
	errValidate interface{}
}{
	{
		errValidate: "missing mode",
	},

	{
		flags:    []string{"-mode", "derpwat"},
		errParse: `invalid value "derpwat"`,
	},

	{
		flags:       []string{"-mode", "swarming"},
		errValidate: "-repository not specified",
	},

	{
		flags: []string{
			"-mode", "swarming", "-revision", "refs/cool/awesome",
		},
		errValidate: "-revision must also be unspecified",
	},

	{
		flags: []string{
			"-mode", "swarming", "-repository", "whatever", "-recipe", "yep",
			"-properties", `{"some": "thing"}`, "-properties-file", "bar",
		},
		errValidate: "only one of -properties or -properties-file",
	},

	{
		flags: []string{
			"-mode", "buildbot",
			"-repository", "something",
			"-revision", "hats",
		},
		errValidate: `invalid revision "hats"`,
	},

	{
		flags: []string{
			"-mode", "buildbot",
			"-checkout-dir", "",
		},
		errValidate: "empty -checkout-dir",
	},

	{
		flags:       []string{"-mode", "buildbot", "-repository", "meep"},
		errValidate: "-recipe is required",
	},

	{
		flags:       []string{"-mode", "swarming", "-workdir", ""},
		errValidate: "-workdir is required",
	},

	{
		flags: []string{
			"-mode", "buildbot",
			"-repository", "meep",
			"-recipe", "cool_recipe",
			"-set-env-abspath", "sup",
		},
		errValidate: "requires a PATH value",
	},

	{
		flags: []string{
			"-mode", "buildbot",
			"-repository", "meep",
			"-properties", `{"something":"awesome"}`,
			"-recipe", "cool_recipe",
		},
		cf: CookFlags{
			Mode:          CookBuildBot,
			RepositoryURL: "meep",
			RecipeName:    "cool_recipe",
			Revision:      "HEAD",
			WorkDir:       "kitchen-workdir",
			CheckoutDir:   "kitchen-checkout",
			Properties: PropertyFlag{
				"something": "awesome",
			},
		},
	},

	{
		flags: []string{
			"-mode", "buildbot",
			"-repository", "meep",
			"-properties", `{"something":"awesome"}`,
			"-temp-dir", "tmp",
			"-recipe", "cool_recipe",
			"-prefix-path-env", "some/dir",
			"-prefix-path-env", "foo",
			"-prefix-path-env", "foo",
			"-set-env-abspath", "DORK=sup",
			"-logdog-tag", "A=B",
			"-logdog-tag", "Roffle=Copter",
		},
		cf: CookFlags{
			Mode:          CookBuildBot,
			RepositoryURL: "meep",
			RecipeName:    "cool_recipe",
			Revision:      "HEAD",
			WorkDir:       "kitchen-workdir",
			CheckoutDir:   "kitchen-checkout",
			PrefixPathENV: []string{
				"$CWD/some/dir",
				"$CWD/foo",
			},
			SetEnvAbspath: []string{
				"DORK=$CWD/sup",
			},
			TempDir: "$CWD/tmp",
			LogDogFlags: LogDogFlags{
				GlobalTags: map[string]string{
					"A":      "B",
					"Roffle": "Copter",
				},
			},
			Properties: PropertyFlag{
				"something": "awesome",
			},
		},
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
								for i, p := range cf.PrefixPathENV {
									cf.PrefixPathENV[i] = r.Replace(p)
								}
								for i, e := range cf.SetEnvAbspath {
									cf.SetEnvAbspath[i] = r.Replace(e)
								}
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
