// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package autotest implements logic necessary for Autotest execution of an
// ExecuteRequest.
package autotest

import (
	"context"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"infra/libs/skylab/autotest/dynamicsuite"
)

// Runner runs a set of tests in autotest.
type Runner struct {
	tests  []*build_api.AutotestTest
	params *test_platform.Request_Params
}

// New returns a new autotest runner.
func New(tests []*build_api.AutotestTest, params *test_platform.Request_Params) *Runner {
	return &Runner{tests, params}
}

// LaunchAndWait launches an autotest execution and waits for it to complete.
func (r *Runner) LaunchAndWait(ctx context.Context, client swarming.Client) error {
	taskID, err := r.launch(ctx, client)
	if err != nil {
		return err
	}

	if err := r.wait(ctx, client, taskID); err != nil {
		return err
	}

	return nil
}

// Response constructs a response based on the current state of the
// Runner.
func (r *Runner) Response(swarming swarming.Client) *steps.ExecuteResponse {
	panic("not yet implemented")
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
	return errors.New("not yet implemented")
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
