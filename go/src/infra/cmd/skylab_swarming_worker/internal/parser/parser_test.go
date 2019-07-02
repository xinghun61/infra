// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package parser

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestParseCmdArgs(t *testing.T) {
	Convey("When parser path and results directory are present, the correct cmd is returned.",
		t, func() {
			a := Args{
				ParserPath: "/opt/infra-tools/autotest_status_parser",
				ResultsDir: "/usr/local/autotest/results/swarming-taskname/1",
			}

			cmd, err := parseCommand(a)
			So(err, ShouldBeNil)
			So(cmd, ShouldNotBeNil)

			got := cmd.Args

			want := []string{
				"/opt/infra-tools/autotest_status_parser",
				"parse",
				"/usr/local/autotest/results/swarming-taskname/1",
			}
			So(want, ShouldResemble, got)
		})
}

func TestMissingParserPath(t *testing.T) {
	Convey("When parser path is missing, an error is returned.",
		t, func() {
			a := Args{
				ResultsDir: "/usr/local/autotest/results/swarming-taskname/1",
			}

			cmd, err := parseCommand(a)
			So(err, ShouldNotBeNil)
			So(cmd, ShouldBeNil)
		})
}

func TestMissingResultsDir(t *testing.T) {
	Convey("When results directory is missing, an error is returned.",
		t, func() {
			a := Args{
				ParserPath: "/opt/infra-tools/autotest_status_parser",
			}

			cmd, err := parseCommand(a)
			So(err, ShouldNotBeNil)
			So(cmd, ShouldBeNil)
		})
}
