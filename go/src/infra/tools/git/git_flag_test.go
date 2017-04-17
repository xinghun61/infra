// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

// TestGitFlags tests GitFlagParser.
func TestGitFlags(t *testing.T) {
	t.Parallel()

	Convey(`Testing GitFlagParser`, t, func() {
		for _, tc := range []struct {
			args []string
			exp  GitArgs
		}{
			{nil, &BaseGitArgs{}},

			{
				[]string{"version"},
				&BaseGitArgs{
					Subcommand:     "version",
					SubcommandArgs: []string{},
				},
			},

			{
				[]string{"pull", "--force"},
				&BaseGitArgs{
					Subcommand:     "pull",
					SubcommandArgs: []string{"--force"},
				},
			},

			{
				[]string{"-C", "path", "status"},
				&BaseGitArgs{
					GitFlags: map[string]string{
						"-C": "path",
					},
					Subcommand:     "status",
					SubcommandArgs: []string{},
				},
			},

			{
				[]string{"-C"},
				&BaseGitArgs{
					Unknown: []string{"-C"},
				},
			},

			{
				[]string{"-C=path", "status"},
				&BaseGitArgs{
					Unknown: []string{"-C=path", "status"},
				},
			},

			{
				[]string{"--no-pager", "clone", "--foo"},
				&GitCloneArgs{
					BaseGitArgs: &BaseGitArgs{
						GitFlags:       map[string]string{"--no-pager": ""},
						Subcommand:     "clone",
						SubcommandArgs: []string{"--foo"},
					},
				},
			},

			{
				[]string{"--no-pager", "-C", "path", "--exec-path=foo", "--git-dir", "bar",
					"fetch", "--depth=1", "-j", "12"},
				&BaseGitArgs{
					GitFlags: map[string]string{
						"--no-pager":  "",
						"-C":          "path",
						"--exec-path": "foo",
						"--git-dir":   "bar",
					},
					Subcommand:     "fetch",
					SubcommandArgs: []string{"--depth=1", "-j", "12"},
				},
			},

			{
				[]string{"-c", "user.email=bob@the.frog", "checkout", "foo", "bar"},
				&BaseGitArgs{
					GitFlags: map[string]string{
						"-c": "user.email=bob@the.frog",
					},
					Subcommand:     "checkout",
					SubcommandArgs: []string{"foo", "bar"},
				},
			},

			{
				[]string{"--some-junk-flag", "subcommand"},
				&BaseGitArgs{
					Unknown: []string{"--some-junk-flag", "subcommand"},
				},
			},
		} {
			Convey(fmt.Sprintf(`Can parse args from: [%s]`, strings.Join(tc.args, " ")), func() {
				So(ParseGitArgs(tc.args...), ShouldResemble, tc.exp)
			})
		}
	})
}

// TestGitCloneFlags tests GitCloneFlagParser.
func TestGitCloneFlags(t *testing.T) {
	t.Parallel()

	Convey(`Testing GitCloneFlagParser`, t, func() {
		for _, tc := range []struct {
			args           []string
			cloneTargetDir string
		}{
			{
				args:           []string{"clone"},
				cloneTargetDir: "",
			},

			{
				args:           []string{"clone", "foo"},
				cloneTargetDir: "foo",
			},

			{
				args:           []string{"clone", "foo", "bar"},
				cloneTargetDir: "bar",
			},

			{
				args:           []string{"clone", "--", "foo", "bar"},
				cloneTargetDir: "bar",
			},

			{
				args:           []string{"clone", "--recurse-submodules=submodules", "foo", "--jobs", "2"},
				cloneTargetDir: "foo",
			},

			{
				args:           []string{"clone", "--recurse-submodules", "--jobs=2", "--separate-git-dir", "foo", "bar", "baz"},
				cloneTargetDir: "baz",
			},

			{
				args:           []string{"clone", "foo", "--recurse-submodules", "bar", "--no-hardlinks"},
				cloneTargetDir: "bar",
			},

			{
				args:           []string{"clone", "--", "foo", "--recurse-submodules", "bar", "--no-hardlinks"},
				cloneTargetDir: "",
			},

			{
				args:           []string{"clone", "--", "foo", "--recurse-submodules"},
				cloneTargetDir: "--recurse-submodules",
			},
		} {
			Convey(fmt.Sprintf(`Can parse clone flags from: [%s] to dir: %q`,
				strings.Join(tc.args, " "), tc.cloneTargetDir), func() {

				ga := ParseGitArgs(tc.args...)
				So(ga, ShouldHaveSameTypeAs, &GitCloneArgs{})

				gca := ga.(*GitCloneArgs)
				So(gca.TargetDir(), ShouldEqual, tc.cloneTargetDir)
			})
		}
	})

	Convey(`Testing clone source repository name`, t, func() {
		for _, tc := range []struct {
			repo  string
			value string
		}{
			{"pants:foo.git/", "foo"},
			{"pants:foo.git", "foo"},
			{"pants:foo/bar", "bar"},
			{"pants:foo/bar.git/baz", "baz"},
			{"https://git.example.com/foo.git", "foo"},
			{"https://git.example.com/foo/bar.git/", "bar"},
			{"https://git.example.com/foo/bar.git/.", ""},
			{"https://git.example.com/foo/bar.git/..", ""},
			{"https://git.example.com/foo/bar/...git", ""},
			{"https://git.example.com/foo/bar.git/.git", ""},
		} {
			Convey(fmt.Sprintf(`Source repository for %q is %q`, tc.repo, tc.value), func() {
				So(sourceRepositoryName(tc.repo), ShouldEqual, tc.value)
			})
		}
	})
}
