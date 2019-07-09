// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package skylab implements logic necessary for Skylab execution of an
// ExecuteRequest.
package skylab

import (
	"context"
	"time"

	"github.com/golang/protobuf/ptypes"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/execution/internal/common"
	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
	"infra/libs/skylab/request"
	"infra/libs/skylab/worker"
)

// TaskSet encapsulates the running state of a set of tasks, to satisfy
// a Skylab Execution.
type TaskSet struct {
	testRuns []*testRun
	params   *test_platform.Request_Params
}

type testRun struct {
	test     *build_api.AutotestTest
	attempts []*attempt
}

func (t *testRun) RequestArgs(params *test_platform.Request_Params) (request.Args, error) {
	isClient, err := t.isClientTest()
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	provisionableDimensions, err := toProvisionableDimensions(params.SoftwareDependencies)
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	timeout, err := toTimeout(params)
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	// TODO(akeshet): Run cmd.Config() with correct environment.
	cmd := &worker.Command{
		TaskName:        t.test.Name,
		ClientTest:      isClient,
		OutputToIsolate: true,
	}

	args := request.Args{
		Cmd:               *cmd,
		SchedulableLabels: toInventoryLabels(params, t.test.Dependencies),
		// TODO(akeshet): Determine parent task ID correctly.
		ParentTaskID: "",
		// TODO(akeshet): Determine priority correctly.
		Priority:                0,
		ProvisionableDimensions: provisionableDimensions,
		// TODO(akeshet): Determine tags correctly.
		SwarmingTags: nil,
		Timeout:      timeout,
	}

	return args, nil
}

func (t *testRun) isClientTest() (bool, error) {
	isClient, ok := isClientTest[t.test.ExecutionEnvironment]
	if !ok {
		return false, errors.Reason("unknown exec environment %s", t.test.ExecutionEnvironment).Err()
	}
	return isClient, nil
}

type attempt struct {
	taskID string
	state  jsonrpc.TaskState
	// Note: If we ever begin supporting other harnesses's result formats
	// then this field will change to a *skylab_test_runner.Result.
	// For now, the autotest-specific variant is more convenient.
	autotestResult *skylab_test_runner.Result_Autotest
}

// NewTaskSet creates a new TaskSet.
func NewTaskSet(tests []*build_api.AutotestTest, params *test_platform.Request_Params) *TaskSet {
	testRuns := make([]*testRun, len(tests))
	for i, test := range tests {
		testRuns[i] = &testRun{test: test}
	}
	return &TaskSet{
		testRuns: testRuns,
		params:   params,
	}
}

// LaunchAndWait launches a skylab execution and waits for it to complete,
// polling for new results periodically (TODO(akeshet): and retrying tests that
// need retry, based on retry policy).
//
// If the supplied context is cancelled prior to completion, or some other error
// is encountered, this method returns whatever partial execution response
// was visible to it prior to that error.
func (r *TaskSet) LaunchAndWait(ctx context.Context, swarming swarming.Client, getter isolate.Getter) error {
	if err := r.launch(ctx, swarming); err != nil {
		return err
	}

	return r.wait(ctx, swarming, getter)
}

var isClientTest = map[build_api.AutotestTest_ExecutionEnvironment]bool{
	build_api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT: true,
	build_api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER: false,
}

func (r *TaskSet) launch(ctx context.Context, swarming swarming.Client) error {
	for _, testRun := range r.testRuns {
		args, err := testRun.RequestArgs(r.params)
		if err != nil {
			return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
		}

		req, err := request.New(args)
		if err != nil {
			return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
		}

		resp, err := swarming.CreateTask(ctx, req)
		if err != nil {
			return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
		}

		logging.Infof(ctx, "Launched test named %s as task %s", testRun.test.Name, swarming.GetTaskURL(resp.TaskId))

		testRun.attempts = append(testRun.attempts, &attempt{taskID: resp.TaskId})
	}
	return nil
}

func (r *TaskSet) wait(ctx context.Context, swarming swarming.Client, getter isolate.Getter) error {
	for {
		complete, err := r.tick(ctx, swarming, getter)
		if complete || err != nil {
			return err
		}

		select {
		case <-ctx.Done():
			return errors.Annotate(ctx.Err(), "wait for tests").Err()
		case <-clock.After(ctx, 15*time.Second):
		}
	}
}

func (r *TaskSet) tick(ctx context.Context, client swarming.Client, getter isolate.Getter) (complete bool, err error) {
	complete = true

	for _, testRun := range r.testRuns {
		attempt := testRun.attempts[len(testRun.attempts)-1]
		if attempt.autotestResult != nil {
			continue
		}

		results, err := client.GetResults(ctx, []string{attempt.taskID})
		if err != nil {
			return false, errors.Annotate(err, "wait for task %s", attempt.taskID).Err()
		}

		result, err := unpackResult(results, attempt.taskID)
		if err != nil {
			return false, errors.Annotate(err, "wait for task %s", attempt.taskID).Err()
		}

		state, err := swarming.AsTaskState(result.State)
		if err != nil {
			return false, errors.Annotate(err, "wait for task %s", attempt.taskID).Err()
		}
		attempt.state = state

		switch {
		// Task ran to completion.
		case swarming.CompletedTaskStates[state]:
			r, err := getAutotestResult(ctx, result.OutputsRef, getter)
			if err != nil {
				return false, errors.Annotate(err, "wait for task %s", attempt.taskID).Err()
			}
			attempt.autotestResult = r
		// Task no longer running, but didn't run to completion.
		case !swarming.UnfinishedTaskStates[state]:
			attempt.autotestResult = &skylab_test_runner.Result_Autotest{Incomplete: true}
		// Task still pending or running; at least 1 task not complete.
		default:
			complete = false
		}
	}

	return complete, nil
}

func toInventoryLabels(params *test_platform.Request_Params, deps []*build_api.AutotestTaskDependency) inventory.SchedulableLabels {
	flatDims := make([]string, len(deps))
	for i, dep := range deps {
		flatDims[i] = dep.Label
	}

	inventory := labels.Revert(flatDims)

	if params.SoftwareAttributes.BuildTarget != nil {
		inventory.Board = &params.SoftwareAttributes.BuildTarget.Name
	}
	if params.HardwareAttributes.Model != "" {
		inventory.Model = &params.HardwareAttributes.Model
	}

	return *inventory
}

func toProvisionableDimensions(deps []*test_platform.Request_Params_SoftwareDependency) ([]string, error) {
	crosBuild, err := common.GetChromeOSBuild(deps)
	if err != nil {
		return nil, errors.Annotate(err, "get provisionable dimensions").Err()
	}
	return []string{"provisionable-cros-version:" + crosBuild}, nil
}

func toTimeout(params *test_platform.Request_Params) (time.Duration, error) {
	if params.Time == nil {
		return 0, errors.Reason("get timeout: nil params.time").Err()
	}
	duration, err := ptypes.Duration(params.Time.MaximumDuration)
	if err != nil {
		return 0, errors.Annotate(err, "get timeout").Err()
	}
	return duration, nil
}

func unpackResult(results []*swarming_api.SwarmingRpcsTaskResult, taskID string) (*swarming_api.SwarmingRpcsTaskResult, error) {
	if len(results) != 1 {
		return nil, errors.Reason("expected 1 result for task id %s, got %d", taskID, len(results)).Err()
	}

	result := results[0]
	if result.TaskId != taskID {
		return nil, errors.Reason("expected result for task id %s, got %s", taskID, result.TaskId).Err()
	}

	return result, nil
}

var taskStateToLifeCycle = map[jsonrpc.TaskState]test_platform.TaskState_LifeCycle{
	jsonrpc.TaskState_BOT_DIED:  test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_CANCELED:  test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_COMPLETED: test_platform.TaskState_LIFE_CYCLE_COMPLETED,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_EXPIRED:     test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_KILLED:      test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_NO_RESOURCE: test_platform.TaskState_LIFE_CYCLE_REJECTED,
	jsonrpc.TaskState_PENDING:     test_platform.TaskState_LIFE_CYCLE_PENDING,
	jsonrpc.TaskState_RUNNING:     test_platform.TaskState_LIFE_CYCLE_RUNNING,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_TIMED_OUT: test_platform.TaskState_LIFE_CYCLE_ABORTED,
}

// Response constructs a response based on the current state of the
// TaskSet.
func (r *TaskSet) Response(swarming swarming.URLer) *steps.ExecuteResponse {
	resp := &steps.ExecuteResponse{}
	resp.TaskResults = toTaskResults(r.testRuns, swarming)

	// TODO(akeshet): Compute overall execution task state.
	return resp
}
