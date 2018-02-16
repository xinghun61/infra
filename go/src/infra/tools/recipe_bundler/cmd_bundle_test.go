// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"strings"
	"testing"

	"go.chromium.org/luci/common/flag/stringmapflag"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestFlagParse(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name   string
		expect string
		input  *cmdBundle
	}{
		{`no repos`, `no repos specified`, &cmdBundle{}},
		{`empty URL`, `repo URL is blank`, &cmdBundle{
			reposInput: stringmapflag.Value{"": "value"},
		}},
	}

	Convey(`Test bad flag parsing`, t, func() {
		for _, tc := range cases {
			tc := tc
			Convey(tc.name, func() {
				_, err := tc.input.parseFlags()
				So(err, ShouldErrLike, tc.expect)
			})
		}
	})
}

func TestRepoInputParsing(t *testing.T) {
	t.Parallel()

	badCases := []struct {
		name   string
		expect string
		input  map[string]string
	}{
		{`bad URL`, `invalid URL escape`, map[string]string{
			"#%%%%%": "value"}},
		{`URL with scheme`, `must not include scheme`, map[string]string{
			"https://foo.bar": "value"}},
		{`Bad ref`, `must start with 'refs/'`, map[string]string{
			"foo.bar/repo.git": "value,something"}},
		{`Bad revision`, `bad revision`, map[string]string{
			"foo.bar/repo.git": "value,refs/something"}},
		{`Bad length`, `wrong length`, map[string]string{
			"foo.bar/repo.git": "f00b45"}},
	}

	Convey(`Test bad parseRepoInput`, t, func() {
		for _, tc := range badCases {
			tc := tc
			Convey(tc.name, func() {
				_, err := parseRepoInput(tc.input)
				So(err, ShouldErrLike, tc.expect)
			})
		}
	})

	goodCases := []struct {
		name   string
		input  map[string]string
		expect map[string]fetchSpec
	}{
		{`basic repo`,
			map[string]string{"foo.bar/repo": ""},
			map[string]fetchSpec{"foo.bar/repo": {"FETCH_HEAD", "HEAD"}}},

		{`basic repo with ref`,
			map[string]string{"foo.bar/repo": "FETCH_HEAD,refs/thingy"},
			map[string]fetchSpec{"foo.bar/repo": {"FETCH_HEAD", "refs/thingy"}}},

		{`basic repo with rev`,
			map[string]string{"foo.bar/repo": strings.Repeat("deadbeef", 5)},
			map[string]fetchSpec{"foo.bar/repo": {strings.Repeat("deadbeef", 5), "HEAD"}}},

		{`basic repo with rev+ref`,
			map[string]string{"foo.bar/repo": strings.Repeat("deadbeef", 5) + ",refs/foobar"},
			map[string]fetchSpec{"foo.bar/repo": {strings.Repeat("deadbeef", 5), "refs/foobar"}}},

		{`basic repo with FETCH_HEAD+HEAD (silly but correct)`,
			map[string]string{"foo.bar/repo": "FETCH_HEAD,HEAD"},
			map[string]fetchSpec{"foo.bar/repo": {"FETCH_HEAD", "HEAD"}}},
	}

	Convey(`Test good parseRepoInput`, t, func() {
		for _, tc := range goodCases {
			tc := tc
			Convey(tc.name, func() {
				ret, err := parseRepoInput(tc.input)
				So(err, ShouldBeNil)
				So(ret, ShouldResemble, tc.expect)
			})
		}
	})

}
