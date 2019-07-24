// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/execution/swarming"
)

type fakeURLer struct{}

func (f *fakeURLer) GetTaskURL(_ string) string {
	return ""
}

var urler swarming.URLer = &fakeURLer{}

// Test that autotest results for a single completed task map correctly.
func TestSingleAutotestTaskResults(t *testing.T) {
	Convey("Given a single task's autotest results", t, func() {
		cases := []struct {
			description   string
			result        *skylab_test_runner.Result_Autotest
			expectVerdict test_platform.TaskState_Verdict
		}{
			// 0 autotest test cases.
			{
				description:   "with no test cases",
				result:        &skylab_test_runner.Result_Autotest{},
				expectVerdict: test_platform.TaskState_VERDICT_NO_VERDICT,
			},

			// 1 autotest test case.
			{
				description: "with 1 passing test case",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_PASSED,
			},
			{
				description: "with 1 failing test case",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_FAILED,
			},
			{
				description: "with 1 undefined-verdict test case",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_UNDEFINED},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_NO_VERDICT,
			},

			// multiple autotest test cases.
			{
				description: "with 2 passing test cases",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_PASSED,
			},
			{
				description: "with 1 passing and 1 undefined-verdict test case",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_UNDEFINED},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_PASSED,
			},
			{
				description: "with 1 passing and 1 failing test case",
				result: &skylab_test_runner.Result_Autotest{
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_FAILED,
			},

			// task with incomplete test cases
			{
				description: "with 1 passing test case, but incomplete results",
				result: &skylab_test_runner.Result_Autotest{
					Incomplete: true,
					TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
						{Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
					},
				},
				expectVerdict: test_platform.TaskState_VERDICT_FAILED,
			},

			// task with no results
			{
				description:   "with no autotest results",
				expectVerdict: test_platform.TaskState_VERDICT_UNSPECIFIED,
			},
		}
		for _, c := range cases {
			Convey(c.description, func() {
				Convey("then task results are correctly converted to verdict.", func() {
					attempt := &attempt{autotestResult: c.result, state: jsonrpc.TaskState_COMPLETED}
					result := toTaskResult("", attempt, 5, urler)
					So(result.State.LifeCycle, ShouldEqual, test_platform.TaskState_LIFE_CYCLE_COMPLETED)
					So(result.State.Verdict, ShouldEqual, c.expectVerdict)
					So(result.Attempt, ShouldEqual, 5)
				})
			})
		}
	})
}
