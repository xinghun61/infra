// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"math/rand"
	"sort"
	"strings"
	"testing"

	"go.chromium.org/luci/vpython/api/vpython"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestPEP425TagSelector(t *testing.T) {
	t.Parallel()

	testCases := []struct {
		goOS     string
		tags     []*vpython.PEP425Tag
		template map[string]string
	}{
		{
			"linux",
			[]*vpython.PEP425Tag{
				{"py2", "none", "any"},
				{"py27", "none", "any"},
				{"cp27", "cp27mu", "linux_x86_64"},
				{"cp27", "cp27mu", "manylinux1_x86_64"},
				{"cp27", "none", "manylinux1_x86_64"},
			},
			map[string]string{
				"platform":    "linux-amd64",
				"py_tag":      "cp27-cp27mu-manylinux1_x86_64",
				"py_python":   "cp27",
				"py_version":  "cp27",
				"py_abi":      "cp27mu",
				"py_platform": "manylinux1_x86_64",
				"py_arch":     "manylinux1_x86_64",
			},
		},

		{
			"darwin",
			[]*vpython.PEP425Tag{
				{"cp27", "cp27m", "macosx_10_12_x86_64"},
				{"cp27", "cp27m", "macosx_10_12_fat64"},
				{"cp27", "cp27m", "macosx_10_12_fat32"},
				{"cp27", "cp27m", "macosx_10_12_intel"},
				{"cp27", "cp27m", "macosx_10_10_intel"},
				{"cp27", "cp27m", "macosx_10_9_fat64"},
				{"cp27", "cp27m", "macosx_10_9_fat32"},
				{"cp27", "cp27m", "macosx_10_9_universal"},
				{"cp27", "cp27m", "macosx_10_8_fat32"},
				{"cp27", "cp27m", "macosx_10_8_universal"},
				{"cp27", "cp27m", "macosx_10_6_intel"},
				{"cp27", "cp27m", "macosx_10_6_fat64"},
				{"cp27", "cp27m", "macosx_10_6_fat32"},
				{"cp27", "cp27m", "macosx_10_6_universal"},
				{"cp27", "cp27m", "macosx_10_5_universal"},
				{"cp27", "cp27m", "macosx_10_4_intel"},
				{"cp27", "cp27m", "macosx_10_4_fat32"},
				{"cp27", "cp27m", "macosx_10_1_universal"},
				{"cp27", "cp27m", "macosx_10_0_fat32"},
				{"cp27", "cp27m", "macosx_10_0_universal"},
				{"cp27", "none", "macosx_10_12_x86_64"},
				{"cp27", "none", "macosx_10_12_intel"},
				{"cp27", "none", "macosx_10_12_fat64"},
				{"cp27", "none", "macosx_10_9_universal"},
				{"cp27", "none", "macosx_10_8_x86_64"},
				{"cp27", "none", "macosx_10_8_intel"},
				{"cp27", "none", "macosx_10_7_intel"},
				{"cp27", "none", "macosx_10_7_fat64"},
				{"cp27", "none", "macosx_10_7_fat32"},
				{"cp27", "none", "macosx_10_6_universal"},
				{"cp27", "none", "macosx_10_5_x86_64"},
				{"cp27", "none", "macosx_10_5_intel"},
				{"cp27", "none", "macosx_10_3_fat32"},
				{"cp27", "none", "macosx_10_3_universal"},
				{"cp27", "none", "macosx_10_2_fat32"},
				{"py2", "none", "macosx_10_4_intel"},
				{"cp27", "none", "any"},
			},
			map[string]string{
				"platform":    "mac-amd64",
				"py_tag":      "cp27-cp27m-macosx_10_4_intel",
				"py_python":   "cp27",
				"py_version":  "cp27",
				"py_abi":      "cp27m",
				"py_platform": "macosx_10_4_intel",
				"py_arch":     "macosx_10_4_intel",
			},
		},

		{
			"linux",
			[]*vpython.PEP425Tag{
				{"py27", "none", "any"},
				{"py27", "none", "linux_i686"},
			},
			map[string]string{
				"platform":    "linux-386",
				"py_tag":      "py27-none-linux_i686",
				"py_python":   "py27",
				"py_version":  "py27",
				"py_abi":      "none",
				"py_platform": "linux_i686",
				"py_arch":     "linux_i686",
			},
		},

		{
			"linux",
			[]*vpython.PEP425Tag{
				{"py27", "none", "any"},
				{"py27", "none", "linux_x86_64"},
			},
			map[string]string{
				"platform":    "linux-amd64",
				"py_tag":      "py27-none-linux_x86_64",
				"py_python":   "py27",
				"py_version":  "py27",
				"py_abi":      "none",
				"py_platform": "linux_x86_64",
				"py_arch":     "linux_x86_64",
			},
		},
	}

	Convey(`Testing PEP425 tag selection`, t, func() {
		for _, randomized := range []bool{
			false,
			true,
		} {
			title := "(Ordered)"
			if randomized {
				title = "(Randomized)"
			}

			Convey(title, func() {
				for i, tc := range testCases {
					tags := tc.tags
					if randomized {
						tags = make([]*vpython.PEP425Tag, len(tc.tags))
						for i, v := range rand.Perm(len(tc.tags)) {
							tags[v] = tc.tags[i]
						}
					}

					tagsStr := make([]string, len(tags))
					for i, tag := range tags {
						tagsStr[i] = tag.TagString()
					}
					t.Logf("Test case #%d, using OS %q, tags: %v", i, tc.goOS, tagsStr)

					// We have to sort the tags list used in the title because Convey
					// statements must be deterministic.
					sort.Strings(tagsStr)
					tagsList := strings.Join(tagsStr, ", ")

					Convey(fmt.Sprintf(`On OS %q, generates template for [%s]`, tc.goOS, tagsList), func() {
						tag := pep425TagSelector(tc.goOS, tags)

						template, err := getPEP425CIPDTemplateForTag(tag)
						So(err, ShouldBeNil)
						So(template, ShouldResemble, tc.template)
					})
				}
			})
		}

		Convey(`Returns an error when no tag is selected.`, func() {
			tag := pep425TagSelector("linux", nil)
			So(tag, ShouldBeNil)

			_, err := getPEP425CIPDTemplateForTag(tag)
			So(err, ShouldErrLike, "no PEP425 tag")
		})

		Convey(`Returns an error when an unknown platform is selected.`, func() {
			tag := pep425TagSelector("linux", []*vpython.PEP425Tag{
				{"py27", "none", "any"},
				{"py27", "foo", "bar"},
			})
			So(tag, ShouldResemble, &vpython.PEP425Tag{Python: "py27", Abi: "foo", Platform: "bar"})

			_, err := getPEP425CIPDTemplateForTag(tag)
			So(err, ShouldErrLike, "failed to infer CIPD platform for tag")
		})
	})
}
