// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package autotest implements logic necessary for Autotest execution of an
// ExecuteRequest.
package autotest

import (
	"context"
	"time"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/cros_test_platform/internal/execution/internal/autotest/parse"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"infra/libs/skylab/autotest/dynamicsuite"
)

// Runner runs a set of tests in autotest.
type Runner struct {
	tests  []*build_api.AutotestTest
	params *test_platform.Request_Params

	response *steps.ExecuteResponse
}

// New returns a new autotest runner.
func New(tests []*build_api.AutotestTest, params *test_platform.Request_Params) *Runner {
	return &Runner{tests: tests, params: params}
}

// LaunchAndWait launches an autotest execution and waits for it to complete.
func (r *Runner) LaunchAndWait(ctx context.Context, client swarming.Client) error {
	taskID, err := r.launch(ctx, client)
	if err != nil {
		return err
	}

	r.response = &steps.ExecuteResponse{State: &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_RUNNING}}

	if err := r.wait(ctx, client, taskID); err != nil {
		return err
	}

	r.response = &steps.ExecuteResponse{State: &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED}}

	resp, err := r.collect(ctx, client, taskID)
	if err != nil {
		return err
	}
	r.response = resp

	return nil
}

// Response constructs a response based on the current state of the
// Runner.
func (r *Runner) Response(swarming swarming.Client) *steps.ExecuteResponse {
	return r.response
}

func (r *Runner) launch(ctx context.Context, client swarming.Client) (string, error) {
	req, err := r.proxyRequest()
	if err != nil {
		return "", errors.Annotate(err, "launch").Err()
	}

	resp, err := client.CreateTask(ctx, req)
	if err != nil {
		return "", errors.Annotate(err, "launch").Err()
	}

	return resp.TaskId, nil
}

func (r *Runner) proxyRequest() (*swarming_api.SwarmingRpcsNewTaskRequest, error) {
	dsArgs := dynamicsuite.Args{
		Board: r.params.SoftwareAttributes.BuildTarget.Name,
		// TODO(akeshet): Determine build from request parameters.
		Build: "",
		Model: r.params.HardwareAttributes.Model,
		// TODO(akeshet): Determine pool from request parameters, after remapping
		// to autotest pool namespace.
		Pool:              "",
		ReimageAndRunArgs: r.reimageAndRunArgs(),
	}

	req, err := dynamicsuite.NewRequest(dsArgs)
	if err != nil {
		return nil, err
	}

	return req, nil
}

func (r *Runner) wait(ctx context.Context, client swarming.Client, taskID string) error {
	for {
		complete, err := r.tick(ctx, client, taskID)
		if complete {
			return nil
		}
		if err != nil {
			return errors.Annotate(err, "wait for task %s completion", taskID).Err()
		}
		select {
		case <-ctx.Done():
			return errors.Annotate(ctx.Err(), "wait for task %s completion", taskID).Err()
		case <-clock.After(ctx, 15*time.Second):
		}
	}
}

func (r *Runner) tick(ctx context.Context, client swarming.Client, taskID string) (complete bool, err error) {
	results, err := client.GetResults(ctx, []string{taskID})
	if err != nil {
		return false, err
	}

	if len(results) != 1 {
		return false, errors.Reason("expected 1 result, found %d", len(results)).Err()
	}

	taskState, err := swarming.AsTaskState(results[0].State)
	if err != nil {
		return false, err
	}

	return !swarming.UnfinishedTaskStates[taskState], nil
}

func (r Runner) collect(ctx context.Context, client swarming.Client, taskID string) (*steps.ExecuteResponse, error) {
	resps, err := client.GetTaskOutputs(ctx, []string{taskID})
	if err != nil {
		return nil, errors.Annotate(err, "collect results").Err()
	}

	if len(resps) != 1 {
		return nil, errors.Reason("collect results: expected 1 result, got %d", len(resps)).Err()
	}

	output := resps[0].Output
	response, err := parse.RunSuite(output)
	if err != nil {
		return nil, errors.Annotate(err, "collect results").Err()
	}

	return response, nil
}

func (r *Runner) reimageAndRunArgs() interface{} {
	testNames := make([]string, len(r.tests))
	for i, v := range r.tests {
		testNames[i] = v.Name
	}
	return map[string]interface{}{
		// test_names is in argument to reimage_and_run which, if provided, short
		// cuts the normal test enumeration code and replaces it with this list
		// of tests.
		// TODO(akeshet): Implement that behavior in autotest.
		"test_names": testNames,
	}
}
