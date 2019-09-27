// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"context"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"math"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/errors"
)

type testRun struct {
	argsGenerator argsGenerator
	Name          string
	maxAttempts   int
	runnable      bool
	attempts      []*attempt
}

func newTestRun(ctx context.Context, invocation *steps.EnumerationResponse_AutotestInvocation, params *test_platform.Request_Params, workerConfig *config.Config_SkylabWorker, parentTaskID string) (*testRun, error) {
	t := testRun{runnable: true, Name: invocation.GetTest().GetName()}
	t.argsGenerator = argsGenerator{invocation: invocation, params: params, workerConfig: workerConfig, parentTaskID: parentTaskID}
	t.maxAttempts = 1 + int(inferTestMaxRetries(invocation))
	return &t, nil
}

func inferTestMaxRetries(inv *steps.EnumerationResponse_AutotestInvocation) int32 {
	if !inv.GetTest().GetAllowRetries() {
		return 0
	}
	return maxInt32IfZero(inv.GetTest().GetMaxRetries())
}

func maxInt32IfZero(v int32) int32 {
	if v == 0 {
		return int32(math.MaxInt32)
	}
	return v
}

func (t *testRun) AttemptsRemaining() int {
	r := t.maxAttempts - len(t.attempts)
	if r > 0 {
		return r
	}
	return 0
}

func (t *testRun) AttemptedAtLeastOnce() bool {
	return len(t.attempts) > 0
}

// ValidateDependencies checks whether this test has dependencies satisfied by
// at least one Skylab bot.
func (t *testRun) ValidateDependencies(ctx context.Context, client swarming.Client) (bool, error) {
	args, err := t.argsGenerator.GenerateArgs(ctx)
	if err != nil {
		return false, errors.Annotate(err, "validate dependencies").Err()
	}
	dims, err := args.StaticDimensions()
	if err != nil {
		return false, errors.Annotate(err, "validate dependencies").Err()
	}
	exists, err := client.BotExists(ctx, dims)
	if err != nil {
		return false, errors.Annotate(err, "validate dependencies").Err()
	}
	return exists, nil
}

func (t *testRun) LaunchAttempt(ctx context.Context, client swarming.Client) error {
	args, err := t.argsGenerator.GenerateArgs(ctx)
	if err != nil {
		return err
	}
	a := attempt{args: args}
	if err := a.Launch(ctx, client); err != nil {
		return err
	}
	t.attempts = append(t.attempts, &a)
	return nil
}

// MarkNotRunnable marks this test run as being unable to run.
//
// In particular, this means that this test run is Completed().
func (t *testRun) MarkNotRunnable() {
	t.runnable = false
}

// Completed determines whether we have completed an attempt for this test.
func (t *testRun) Completed() bool {
	if !t.runnable {
		return true
	}
	a := t.GetLatestAttempt()
	return a != nil && a.Completed()
}

func (t *testRun) TaskResult(urler swarming.URLer) []*steps.ExecuteResponse_TaskResult {
	if !t.runnable {
		return []*steps.ExecuteResponse_TaskResult{
			{
				Name: t.Name,
				State: &test_platform.TaskState{
					LifeCycle: test_platform.TaskState_LIFE_CYCLE_REJECTED,
					Verdict:   test_platform.TaskState_VERDICT_UNSPECIFIED,
				},
			},
		}
	}

	ret := make([]*steps.ExecuteResponse_TaskResult, len(t.attempts))
	for i, a := range t.attempts {
		ret[i] = toTaskResult(t.Name, a, i, urler)
	}
	return ret
}

func (t *testRun) Verdict() test_platform.TaskState_Verdict {
	if !t.runnable {
		return test_platform.TaskState_VERDICT_UNSPECIFIED
	}
	failedEarlierAttempt := false
	for _, a := range t.attempts {
		switch a.Verdict() {
		case test_platform.TaskState_VERDICT_NO_VERDICT:
			return test_platform.TaskState_VERDICT_NO_VERDICT
		case test_platform.TaskState_VERDICT_PASSED:
			if failedEarlierAttempt {
				return test_platform.TaskState_VERDICT_PASSED_ON_RETRY
			}
			return test_platform.TaskState_VERDICT_PASSED
		case test_platform.TaskState_VERDICT_FAILED,
			test_platform.TaskState_VERDICT_UNSPECIFIED:
			failedEarlierAttempt = true
		default:
			return test_platform.TaskState_VERDICT_FAILED
		}
	}
	return test_platform.TaskState_VERDICT_FAILED
}

func (t *testRun) GetLatestAttempt() *attempt {
	if len(t.attempts) == 0 {
		return nil
	}
	return t.attempts[len(t.attempts)-1]
}
