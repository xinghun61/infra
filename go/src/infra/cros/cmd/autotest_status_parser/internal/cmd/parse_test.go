// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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

func TestParseResultsFile(t *testing.T) {
	Convey("When a status.log with various test results is parsed, the results are correct.",
		t, func() {
			// Input format: each line consists of strings separated by tab characters,
			// the first three strings in a line represent the test status, test
			// directory and test name (see README.md for a detailed description).
			input := `
START	IgnoredDir	Ignored	Ignore lines not starting with "END ".
GOOD	IgnoredDir	Ignored
END GOOD	PassDir	Pass
END GOOD	----	Directoryless	Tests may have no dir.
END WARN	WarnDir	Warn	WARN is a passing status.
END FAIL	FailDir	Fail
END ERROR	ErrorDir	Error
END WEIRD	WeirdDir	WeirdStatus	Report unknown status strings as failing.
END FAIL	NamelessDir	----	Fall back to dir name for nameless tests.
				END FAIL	ManyTabsDir	ManyTabs	Ignore initial tabs.
END FAIL	----	----	Ignore tests without a name and a dir.
END FAIL	----	reboot	Ignore tests named reboot.
END GOOD	Ignore incomplete lines.
  AutoservRunError: command execution error
  stderr:
  This is ignored.`
			got := parseResultsFile(input)

			want := []*skylab_test_runner.Result_Autotest_TestCase{
				testCase("Pass", true),
				testCase("Directoryless", true),
				testCase("Warn", true),
				testCase("Fail", false),
				testCase("Error", false),
				testCase("WeirdStatus", false),
				testCase("NamelessDir", false),
				testCase("ManyTabs", false),
			}
			So(want, ShouldResemble, got)
		})
}

func TestEmptyResultFile(t *testing.T) {
	Convey("When an empty status.log is parsed, there are no results.", t, func() {
		input := ""
		got := parseResultsFile(input)

		want := []*skylab_test_runner.Result_Autotest_TestCase(nil)
		So(want, ShouldResemble, got)
	})
}

func testCase(name string, passed bool) *skylab_test_runner.Result_Autotest_TestCase {
	output := skylab_test_runner.Result_Autotest_TestCase{
		Name:    name,
		Verdict: verdict[passed],
	}
	return &output
}
