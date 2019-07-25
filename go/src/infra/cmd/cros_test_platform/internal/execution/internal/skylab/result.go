// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"bytes"
	"context"
	"fmt"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/logging"

	"github.com/golang/protobuf/jsonpb"

	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
)

const resultsFileName = "results.json"

func getAutotestResult(ctx context.Context, sResult *swarming_api.SwarmingRpcsTaskResult, gf isolate.GetterFactory) (*skylab_test_runner.Result_Autotest, error) {
	if sResult == nil {
		return nil, errors.Reason("get result: nil swarming result").Err()
	}

	taskID := sResult.TaskId
	outputRef := sResult.OutputsRef
	if outputRef == nil {
		logging.Debugf(ctx, "task %s has no output ref, considering it failed due to incompleteness", taskID)
		return &skylab_test_runner.Result_Autotest{Incomplete: true}, nil
	}

	getter, err := gf(ctx, outputRef.Isolatedserver)
	if err != nil {
		return nil, errors.Annotate(err, "get result").Err()
	}

	logging.Debugf(ctx, "fetching result for task %s from isolate ref %+v", taskID, outputRef)
	content, err := getter.GetFile(ctx, isolated.HexDigest(outputRef.Isolated), resultsFileName)
	if err != nil {
		return nil, errors.Annotate(err, "get result for task %s", taskID).Err()
	}

	var result skylab_test_runner.Result

	err = jsonpb.Unmarshal(bytes.NewReader(content), &result)
	if err != nil {
		return nil, errors.Annotate(err, "get result for task %s", taskID).Err()
	}

	a := result.GetAutotestResult()
	if a == nil {
		return nil, errors.Reason("get result for task %s: no autotest result; other harnesses not yet supported", taskID).Err()
	}

	return a, nil
}

func toTaskResults(testRuns []*testRun, urler swarming.URLer) []*steps.ExecuteResponse_TaskResult {
	var results []*steps.ExecuteResponse_TaskResult
	for _, test := range testRuns {
		for num, attempt := range test.attempts {
			results = append(results, toTaskResult(test.test.Name, attempt, num, urler))
		}
	}
	return results
}

func toTaskResult(testName string, attempt *attempt, attemptNum int, urler swarming.URLer) *steps.ExecuteResponse_TaskResult {
	var verdict test_platform.TaskState_Verdict

	switch {
	case attempt.autotestResult == nil:
		verdict = test_platform.TaskState_VERDICT_UNSPECIFIED
	case attempt.autotestResult.Incomplete:
		verdict = test_platform.TaskState_VERDICT_FAILED
	default:
		verdict = flattenToVerdict(attempt.autotestResult.TestCases)
	}

	// TODO(akeshet): Determine this URL in a more principled way. See crbug.com/987487
	// for context.
	logURL := fmt.Sprintf(
		"https://stainless.corp.google.com/browse/chromeos-autotest-results/swarming-%s/",
		attempt.taskID,
	)

	return &steps.ExecuteResponse_TaskResult{
		Name: testName,
		State: &test_platform.TaskState{
			LifeCycle: taskStateToLifeCycle[attempt.state],
			Verdict:   verdict,
		},
		TaskUrl: urler.GetTaskURL(attempt.taskID),
		LogUrl:  logURL,
		Attempt: int32(attemptNum),
	}
}

func flattenToVerdict(tests []*skylab_test_runner.Result_Autotest_TestCase) test_platform.TaskState_Verdict {
	// By default (if no test cases ran), then there is no verdict.
	verdict := test_platform.TaskState_VERDICT_NO_VERDICT
	for _, c := range tests {
		switch c.Verdict {
		case skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL:
			// Any case failing means the flat verdict is a failure.
			return test_platform.TaskState_VERDICT_FAILED
		case skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS:
			// Otherwise, at least 1 passing verdict means a pass.
			verdict = test_platform.TaskState_VERDICT_PASSED
		case skylab_test_runner.Result_Autotest_TestCase_VERDICT_UNDEFINED:
			// Undefined verdicts do not affect flat verdict.
		}
	}
	return verdict
}
