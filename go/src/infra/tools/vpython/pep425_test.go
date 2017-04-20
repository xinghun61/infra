// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"strings"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/vpython/api/vpython"

	. "github.com/smartystreets/goconvey/convey"
)

func mkTag(version, abi, arch string) *vpython.Environment_Pep425Tag {
	return &vpython.Environment_Pep425Tag{
		Version: version,
		Abi:     abi,
		Arch:    arch,
	}
}

func TestPEP425TagSelector(t *testing.T) {
	t.Parallel()

	Convey(`Testing PEP425 tag selection`, t, func() {
		c := context.Background()

		for _, tc := range []struct {
			tags     []*vpython.Environment_Pep425Tag
			template map[string]string
		}{
			{nil, nil},

			{
				[]*vpython.Environment_Pep425Tag{
					mkTag("py2", "none", "any"),
					mkTag("py27", "none", "any"),
					mkTag("cp27", "cp27mu", "linux_x86_64"),
					mkTag("cp27", "cp27mu", "manylinux1_x86_64"),
				},
				map[string]string{
					"py_tag":     "cp27-cp27mu-manylinux1_x86_64",
					"py_version": "cp27",
					"py_abi":     "cp27mu",
					"py_arch":    "manylinux1_x86_64",
				},
			},

			{
				[]*vpython.Environment_Pep425Tag{
					mkTag("py27", "none", "any"),
					mkTag("py27", "foo", "bar"),
				},
				map[string]string{
					"py_tag":     "py27-foo-bar",
					"py_version": "py27",
					"py_abi":     "foo",
					"py_arch":    "bar",
				},
			},

			{
				[]*vpython.Environment_Pep425Tag{
					mkTag("py27", "none", "any"),
					mkTag("py27", "none", "linux_386"),
				},
				map[string]string{
					"py_tag":     "py27-none-linux_386",
					"py_version": "py27",
					"py_abi":     "none",
					"py_arch":    "linux_386",
				},
			},

			{
				[]*vpython.Environment_Pep425Tag{
					mkTag("py27", "none", "any"),
					mkTag("py27", "cp27mu", "any"),
				},
				map[string]string{
					"py_tag":     "py27-cp27mu-any",
					"py_version": "py27",
					"py_abi":     "cp27mu",
					"py_arch":    "any",
				},
			},
		} {
			tagsStr := make([]string, len(tc.tags))
			for i, other := range tc.tags {
				tagsStr[i] = other.TagString()
			}

			Convey(fmt.Sprintf(`Generates template for [%s]`, strings.Join(tagsStr, ", ")), func() {
				env := vpython.Environment{
					Pep425Tag: tc.tags,
				}

				template, err := getCIPDTemplatesForEnvironment(c, &env)
				So(err, ShouldBeNil)
				So(template, ShouldResemble, tc.template)
			})
		}
	})
}
