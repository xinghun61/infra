// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package cmd

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
)

var verdict = map[bool]skylab_test_runner.Result_Autotest_TestCase_Verdict{
	true:  skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS,
	false: skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL,
}

// parseResultsFile tests

func TestEmptyResultFile(t *testing.T) {
	Convey("When an empty status.log is parsed, there are no results.", t, func() {
		input := ""
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase(nil)
		So(got, ShouldResemble, want)
	})
}

func TestPass(t *testing.T) {
	Convey("When status.log contains a GOOD status with a test name, a passing test is returned.", t, func() {
		// Input format: each line consists of strings separated by tab characters,
		// the first three strings in a line represent the test status, test
		// directory and test name, the last string when present represents a
		// comment (see README.md for a detailed description).
		input := `
START	----	Pass
	GOOD	----	----
END GOOD	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("Pass", true, ""),
		}
		So(got, ShouldResemble, want)
	})
}

func TestWarn(t *testing.T) {
	Convey("When status.log contains a WARN status, a passing test with a comment is returned.", t, func() {
		input := `
START	----	Warn
	WARN	----	----	This is a warning.
END WARN	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("Warn", true, "This is a warning.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestFail(t *testing.T) {
	Convey("When status.log contains a FAIL status, a test failure with a comment is returned.", t, func() {
		input := `
START	----	Fail
	FAIL	----	----	Something failed.
END FAIL	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("Fail", false, "Something failed.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestError(t *testing.T) {
	Convey("When status.log contains an ERROR status, a test failure with a comment is returned.", t, func() {
		input := `
START	----	Error
	ERROR	----	----	An error occured.
END ERROR	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("Error", false, "An error occured.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestTestNA(t *testing.T) {
	Convey("When status.log contains an TEST_NA status, a test failure with a comment is returned (crbug.com/846770).", t, func() {
		input := `
START	----	TestNA
	TEST_NA	----	----	The DUT is missing a necessary gadget.
END TEST_NA	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("TestNA", false, "The DUT is missing a necessary gadget.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestUnrecognizedEventType(t *testing.T) {
	Convey("When status.log contains an unrecognized event, a test failure without a comment is returned.", t, func() {
		input := `
START	----	WeirdStatus
	WEIRD	----	----	Comments about unrecognized status values are ignored.
END WEIRD	----	----
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("WeirdStatus", false, ""),
		}
		So(got, ShouldResemble, want)
	})
}

func TestNameless(t *testing.T) {
	Convey("When a test has no name the directory name is used instead.", t, func() {
		input := `
Fall back to dir name for nameless tests.
START	NamelessDir	----
	GOOD	Ignored	Ignored
END GOOD	Ignored	Ignored
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("NamelessDir", true, ""),
		}
		So(got, ShouldResemble, want)
	})
}

func TestComments(t *testing.T) {
	Convey("When there are comments, only the ones from specific event lines are surfaced.", t, func() {
		input := `
Comments that don't match the event line format (at least 3 strings separated by tabs) are ignored.
START	----	WithoutComments
	GOOD	----	----	Comments about "GOOD" tests are ignored.
END GOOD	----	----
START	----	WithComments	START comments are ignored.
	INFO	----	----	INFO comments are ignored.
	WARN	----	----	This comment is ignored because there's a string after it.	This is a warning.
Comments can be anywhere.
	WARN	----	----	There's more to say about the warning.
	WARN	----	----	This comment is ignored because there's a tab after it.	
END WARN	----	----	END comments are ignored.
	stderr:
More logging that is ignored.
`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("WithoutComments", true, ""),
			testCase("WithComments", true, "This is a warning.\nThere's more to say about the warning.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestIgnoredFields(t *testing.T) {
	Convey("When a test name is provided in the START event, directory name is ignored and test name provided in other events is also ignored.", t, func() {
		input := `
START	Ignored	Test-Name
	INFO	Ignored	Ignored	Ignored.
	FAIL	Ignored	Ignored	Not ignored.
END FAIL	Ignored	Ignored

`
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase{
			testCase("Test-Name", false, "Not ignored.\n"),
		}
		So(got, ShouldResemble, want)
	})
}

func TestIgnoredTestNames(t *testing.T) {
	Convey("When a test name is 'reboot' or both test name and directory name are missing, ignore the test.", t, func() {
		input := `
START	----	----
	FAIL	Ignored	Ignored	Something failed.
END FAIL	Ignored	Ignored

Ignore tests named reboot.
START	----	reboot
	FAIL	Ignored	Ignored	Something failed.
END FAIL	Ignored	Ignored
`
		got := parseResultsFile(input)

		So(got, ShouldBeNil)
	})
}

func TestNestedTestCases(t *testing.T) {
	Convey("When the test cases are nested, the verdicts are correctly attributed to test cases.",
		t, func() {
			input := `
START	----	NestedTest
	START	----	SubTest1
		WARN	----	----	A subtest warning.
	END WARN	----	----
	START	----	SubTest2
		START	----	SubSubTest
			ERROR	----	----	The outer tests don't care about this error.
		END ERROR	----	----
		GOOD	----	----	Subtest succeeded.
	END GOOD	----	----
	FAIL	----	----	A failure of the outer test.
END FAIL	----	----
`
			got := parseResultsFile(input)

			want := []*skylab_test_runner.Result_Autotest_TestCase{
				testCase("SubTest1", true, "A subtest warning.\n"),
				testCase("SubSubTest", false, "The outer tests don't care about this error.\n"),
				testCase("SubTest2", true, ""),
				testCase("NestedTest", false, "A failure of the outer test.\n"),
			}
			So(got, ShouldResemble, want)
		})
}

func TestUnfinishedTestCases(t *testing.T) {
	Convey("When test cases don't have an 'END ...' event, declare them failed.",
		t, func() {
			input := `
START	----	CrashedOuter
	START	----	CrashedMiddle
		START	----	CrashedInner
			WARN	----	----	Something bad is happening.
	AutoservRunError: command execution error
  stderr:
  A stack trace that is ignored.`
			got := parseResultsFile(input)

			want := []*skylab_test_runner.Result_Autotest_TestCase{
				testCase("CrashedInner", false, "Something bad is happening.\n"),
				testCase("CrashedMiddle", false, ""),
				testCase("CrashedOuter", false, ""),
			}
			So(got, ShouldResemble, want)
		})
}

func TestContradictoryVerdicts(t *testing.T) {
	Convey("When an event string disagrees with the 'END ' string, the ends string wins.",
		t, func() {
			input := `
START	----	ActuallyPasses
	FAIL	----	----	This test actually succeeds.
END GOOD	----	----

START	----	ActuallyFails
	GOOD	----	----	Nothing could go wrong.
END ERROR	----	----
`
			got := parseResultsFile(input)

			want := []*skylab_test_runner.Result_Autotest_TestCase{
				testCase("ActuallyPasses", true, "This test actually succeeds.\n"),
				testCase("ActuallyFails", false, ""),
			}
			So(got, ShouldResemble, want)
		})
}

// Exit code file tests

func TestExitedWithoutErrors(t *testing.T) {
	Convey("When exit code is zero, report no exit errors",
		t, func() {
			// Input format: three lines, each containing an integer. The integer on
			// the second line is the exit status code.
			input := "42\n0\n0"

			So(exitedWithErrors(input), ShouldResemble, false)
		})
}

func TestExitedWithErrors(t *testing.T) {
	Convey("When the server job was aborted, report exit error",
		t, func() {
			// 256 = Exited with status 1.
			input := "42\n256\n0"

			So(exitedWithErrors(input), ShouldResemble, true)
		})
}

func TestAborted(t *testing.T) {
	Convey("When the server job was aborted, report exit error",
		t, func() {
			// 9 = Killed.
			input := "42\n9\n0"

			So(exitedWithErrors(input), ShouldResemble, true)
		})
}

func TestFailedToParseExitCode(t *testing.T) {
	Convey("When the exit code is not an integer, report exit error.",
		t, func() {
			input := "42\nnot_an_integer\n0"

			So(exitedWithErrors(input), ShouldResemble, true)
		})
}

func TestMissingExitCode(t *testing.T) {
	Convey("When the exit code is missing, report exit error.",
		t, func() {
			input := "42"

			So(exitedWithErrors(input), ShouldResemble, true)
		})
}

func TestEmptyExitStatusFile(t *testing.T) {
	Convey("When the exit status file is empty, report exit error.",
		t, func() {
			input := ""

			So(exitedWithErrors(input), ShouldResemble, true)
		})
}

func testCase(name string, passed bool, summary string) *skylab_test_runner.Result_Autotest_TestCase {
	output := skylab_test_runner.Result_Autotest_TestCase{
		Name:                 name,
		Verdict:              verdict[passed],
		HumanReadableSummary: summary,
	}
	return &output
}
