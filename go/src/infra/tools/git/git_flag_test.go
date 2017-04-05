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
			{nil, GitArgs{}},

			{
				[]string{"version"},
				GitArgs{
					GitFlags:       []string{},
					Subcommand:     "version",
					SubcommandArgs: []string{},
				},
			},

			{
				[]string{"pull", "--force"},
				GitArgs{
					GitFlags:       []string{},
					Subcommand:     "pull",
					SubcommandArgs: []string{"--force"},
				},
			},

			{
				[]string{"-C", "path", "status"},
				GitArgs{
					GitFlags:       []string{"-C", "path"},
					Subcommand:     "status",
					SubcommandArgs: []string{},
				},
			},

			{
				[]string{"-C"},
				GitArgs{
					GitFlags:       []string{"-C"},
					Subcommand:     "",
					SubcommandArgs: nil,
				},
			},

			{
				[]string{"-C=path", "status"},
				GitArgs{
					GitFlags:       []string{},
					Subcommand:     "-C=path",
					SubcommandArgs: []string{"status"},
				},
			},

			{
				[]string{"--no-pager", "-C", "path", "--exec-path=foo", "--git-dir", "bar",
					"fetch", "--depth=1", "-j", "12"},
				GitArgs{
					GitFlags:       []string{"--no-pager", "-C", "path", "--exec-path=foo", "--git-dir", "bar"},
					Subcommand:     "fetch",
					SubcommandArgs: []string{"--depth=1", "-j", "12"},
				},
			},

			{
				[]string{"-c", "user.email=bob@the.frog", "checkout", "foo", "bar"},
				GitArgs{
					GitFlags:       []string{"-c", "user.email=bob@the.frog"},
					Subcommand:     "checkout",
					SubcommandArgs: []string{"foo", "bar"},
				},
			},

			{
				[]string{"--some-junk-flag", "subcommand"},
				GitArgs{
					GitFlags:       []string{},
					Subcommand:     "--some-junk-flag",
					SubcommandArgs: []string{"subcommand"},
				},
			},
		} {
			Convey(fmt.Sprintf(`Can parse args from: [%s]`, strings.Join(tc.args, " ")), func() {
				So(parseGitArgs(tc.args...), ShouldResemble, tc.exp)
			})
		}
	})
}
