// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package proxy provides a library to create swarming requests for an
// autotest-swarming-proxy task.
package proxy

import (
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

const runSuitePath = "/usr/local/autotest/site_utils/run_suite.py"

// RunSuiteArgs defines the set of arguments for creating a run_suite request.
type RunSuiteArgs struct {
	Build     string
	Board     string
	Model     string
	SuiteName string
	Pool      string
}

// NewRunSuite creates a new swarming request for the given run suite args.
func NewRunSuite(args RunSuiteArgs) *swarming.SwarmingRpcsNewTaskRequest {
	cmd := runSuiteCmd(args)
	req := &swarming.SwarmingRpcsNewTaskRequest{
		// TODO(akeshet): Match the current naming scheme e.g.
		// coral-release/R75-12105.78.0-paygen_au_stable
		Name:       args.SuiteName,
		TaskSlices: asSlices(cmd),
	}
	return req
}

func runSuiteCmd(args RunSuiteArgs) []string {
	cmd := []string{runSuitePath}

	if args.Build != "" {
		cmd = append(cmd, "--build", args.Build)
	}
	if args.Board != "" {
		cmd = append(cmd, "--board", args.Board)
	}
	if args.Model != "" {
		cmd = append(cmd, "--model", args.Model)
	}
	if args.SuiteName != "" {
		cmd = append(cmd, "--suite_name", args.SuiteName)
	}
	if args.Pool != "" {
		cmd = append(cmd, "--pool", args.Pool)
	}
	return cmd
}

func asSlices(cmd []string) []*swarming.SwarmingRpcsTaskSlice {
	slices := make([]*swarming.SwarmingRpcsTaskSlice, 1)
	slices[0] = &swarming.SwarmingRpcsTaskSlice{
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command: cmd,
			// TODO(akeshet): Add additional necessary properties, such as
			// priority, pool dimension, timeout, etc.
		},
	}
	return slices
}
