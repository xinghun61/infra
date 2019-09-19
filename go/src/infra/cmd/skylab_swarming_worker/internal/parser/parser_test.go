// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package parser

import (
	"bytes"
	"strings"
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

func TestPassingRun(t *testing.T) {
	Convey("When the run succeeded, test cases are annotated and no autoserv failure is reported.",
		t, func() {
			input := []byte(`
{
	"autotestResult": {
		"testCases": [
		{
			"name": "passing_test_case",
			"verdict": "VERDICT_PASS"
		}]
	},
	"prejob": {
		"step": [
		{
			"name": "provision",
			"verdict": "VERDICT_PASS"
		}]
	}
}`)

			var output bytes.Buffer

			annotateTestCases(input, false, &output)

			got := output.String()

			got = checkOneTestCase(got, "provision", false, "")
			got = checkOneTestCase(got, "passing_test_case", false, "")

			So(strings.Index(got, "@@@"), ShouldEqual, -1)
		})
}

func TestFailingTestCase(t *testing.T) {
	Convey("When test cases failed, they are annotated and no autoserv failure is reported.",
		t, func() {
			input := []byte(`
{
	"autotestResult": {
		"testCases": [
		{
			"name": "passing_test_case",
			"verdict": "VERDICT_PASS"
		},
		{
			"name": "failing_test_case",
			"verdict": "VERDICT_FAIL",
			"humanReadableSummary": "Failure because reasons."
		},
		{
			"name": "mystery_test_case"
		}]
	},
	"prejob": {
		"step": [
		{
			"name": "provision",
			"verdict": "VERDICT_PASS"
		}]
	}
}`)

			var output bytes.Buffer

			annotateTestCases(input, true, &output)

			got := output.String()

			got = checkOneTestCase(got, "provision", false, "")
			got = checkOneTestCase(got, "passing_test_case", false, "")
			got = checkOneTestCase(got, "failing_test_case", true, "Failure because reasons.")
			got = checkOneTestCase(got, "mystery_test_case", true, "")

			So(strings.Index(got, "@@@"), ShouldEqual, -1)
		})
}

func TestFailingPrejob(t *testing.T) {
	Convey("When prejob failed, it is annotated and no autoserv failure is reported.",
		t, func() {
			input := []byte(`
{
	"autotestResult": {
		"incomplete": true
	},
	"prejob": {
		"step": [
		{
			"name": "provision",
			"verdict": "VERDICT_FAIL",
			"humanReadableSummary": "The DUT exploded."
		}]
	}
}`)

			var output bytes.Buffer

			annotateTestCases(input, true, &output)

			got := output.String()

			got = checkOneTestCase(got, "provision", true, "The DUT exploded.")

			So(strings.Index(got, "@@@"), ShouldEqual, -1)
		})
}

func TestAutoservFailure(t *testing.T) {
	Convey("When a run fails with no individual tests failing, autoserv failure is reported.",
		t, func() {
			input := []byte(`
{
	"autotestResult": {
		"testCases": [
		{
			"name": "passing_test_case",
			"verdict": "VERDICT_PASS"
		}],
		"incomplete": true
	},
	"prejob": {
		"step": [
		{
			"name": "provision",
			"verdict": "VERDICT_PASS"
		}]
	}
}`)

			var output bytes.Buffer

			annotateTestCases(input, true, &output)

			got := output.String()

			got = checkOneTestCase(got, "provision", false, "")
			got = checkOneTestCase(got, "passing_test_case", false, "")
			got = checkOneTestCase(got, "autoserv", true, "")

			So(strings.Index(got, "@@@"), ShouldEqual, -1)
		})
}

func checkOneTestCase(input string, name string, failed bool, summary string) string {
	input = checkNextAnnotation(input, "SEED_STEP "+name)
	input = checkNextAnnotation(input, "STEP_CURSOR "+name)
	input = checkNextAnnotation(input, "STEP_NEST_LEVEL@1")
	input = checkNextAnnotation(input, "STEP_STARTED")

	So(input, ShouldContainSubstring, summary)

	if failed {
		input = checkNextAnnotation(input, "STEP_FAILURE")
	}
	input = checkNextAnnotation(input, "STEP_CLOSED")
	input = checkNextAnnotation(input, "STEP_CURSOR Test results")

	return input
}

func checkNextAnnotation(s string, want string) string {
	start := strings.Index(s, "@@@") + 3
	s = s[start:]
	end := strings.Index(s, "@@@")

	So(s[:end], ShouldResemble, want)
	return s[end+3:]
}
