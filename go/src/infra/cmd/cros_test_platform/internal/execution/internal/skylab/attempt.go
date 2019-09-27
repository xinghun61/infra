// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"context"
	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"infra/libs/skylab/request"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/swarming/proto/jsonrpc"
)

type attempt struct {
	args   request.Args
	taskID string
	state  jsonrpc.TaskState
	// Note: If we ever begin supporting other harnesses's result formats
	// then this field will change to a *skylab_test_runner.Result.
	// For now, the autotest-specific variant is more convenient.
	autotestResult *skylab_test_runner.Result_Autotest
}

func (a *attempt) TaskName() string {
	return a.args.Cmd.TaskName
}

func (a *attempt) Launch(ctx context.Context, client swarming.Client) error {
	req, err := a.args.SwarmingNewTaskRequest()
	if err != nil {
		return errors.Annotate(err, "launch attempt for %s", a.TaskName()).Err()
	}
	resp, err := client.CreateTask(ctx, req)
	if err != nil {
		return errors.Annotate(err, "launch attempt for %s", a.TaskName()).Err()
	}
	a.taskID = resp.TaskId
	logging.Infof(ctx, "Launched attempt for %s as task %s", a.TaskName(), client.GetTaskURL(a.taskID))
	return nil
}

// Completed returns whether the current attempt is complete.
func (a *attempt) Completed() bool {
	return a.autotestResult != nil
}

func (a *attempt) Verdict() test_platform.TaskState_Verdict {
	if !a.Completed() {
		return test_platform.TaskState_VERDICT_UNSPECIFIED
	}
	if a.autotestResult == nil {
		return test_platform.TaskState_VERDICT_UNSPECIFIED
	}
	if a.autotestResult.Incomplete {
		return test_platform.TaskState_VERDICT_FAILED
	}

	// By default (if no test cases ran), then there is no verdict.
	verdict := test_platform.TaskState_VERDICT_NO_VERDICT
	for _, c := range a.autotestResult.GetTestCases() {
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

// FetchResults fetches the latest swarming and isolate state of the given attempt,
// and updates the attempt accordingly.
func (a *attempt) FetchResults(ctx context.Context, client swarming.Client, gf isolate.GetterFactory) error {
	results, err := client.GetResults(ctx, []string{a.taskID})
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}
	result, err := unpackResult(results, a.taskID)
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}
	state, err := swarming.AsTaskState(result.State)
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}
	a.state = state

	switch {
	// Task ran to completion.
	case swarming.CompletedTaskStates[state]:
		r, err := getAutotestResult(ctx, result, gf)
		if err != nil {
			logging.Debugf(ctx, "failed to fetch autotest results for task %s due to error '%s', treating its results as incomplete (failure)", a.taskID, err.Error())
			r = &skylab_test_runner.Result_Autotest{Incomplete: true}
		}
		a.autotestResult = r
	// Task no longer running, but didn't run to completion.
	case !swarming.UnfinishedTaskStates[state]:
		a.autotestResult = &skylab_test_runner.Result_Autotest{Incomplete: true}
	// Task is still running.
	default:
	}
	return nil
}
