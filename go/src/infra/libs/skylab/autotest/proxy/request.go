// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package proxy provides a library to create swarming requests for an
// autotest-swarming-proxy task.
package proxy

import (
	"encoding/json"
	"strconv"
	"time"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
)

const runSuitePath = "/usr/local/autotest/site_utils/run_suite.py"

// RunSuiteArgs defines the set of arguments for creating a run_suite request.
type RunSuiteArgs struct {
	Build           string
	FirmwareRWBuild string
	FirmwareROBuild string
	Board           string
	Model           string
	SuiteName       string
	Pool            string
	Priority        int
	AfeHost         string
	Timeout         time.Duration
	// SuiteArgs are the arguments to be passed into the suite. This object
	// must be json-encodable, or an error will be returned.
	SuiteArgs interface{}
}

// NewRunSuite creates a new swarming request for the given run suite args.
func NewRunSuite(args RunSuiteArgs) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	cmd, err := runSuiteCmd(args)
	if err != nil {
		return nil, errors.Annotate(err, "new run suite").Err()
	}
	req := &swarming.SwarmingRpcsNewTaskRequest{
		// TODO(akeshet): Match the current naming scheme e.g.
		// coral-release/R75-12105.78.0-paygen_au_stable
		Name:       args.SuiteName,
		TaskSlices: asSlices(cmd, args.Timeout),
	}
	return req, nil
}

func runSuiteCmd(args RunSuiteArgs) ([]string, error) {
	cmd := []string{runSuitePath}

	cmd = append(cmd, "--json_dump_postfix")

	if args.Build != "" {
		cmd = append(cmd, "--build", args.Build)
	}
	if args.FirmwareROBuild != "" {
		cmd = append(cmd, "--firmware_ro_build", args.FirmwareROBuild)
	}
	if args.FirmwareRWBuild != "" {
		cmd = append(cmd, "--firmware_rw_build", args.FirmwareRWBuild)
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
	if args.Priority > 0 {
		cmd = append(cmd, "--priority", strconv.Itoa(args.Priority))
	}
	if args.AfeHost != "" {
		cmd = append(cmd, "-w", args.AfeHost)
	}
	if args.Timeout != 0 {
		minutes := int(args.Timeout.Minutes())
		cmd = append(cmd, "--timeout_mins", strconv.Itoa(minutes))
	}
	if args.SuiteArgs != nil {
		bytes, err := json.Marshal(args.SuiteArgs)
		if err != nil {
			return nil, errors.Annotate(err, "create command").Err()
		}
		cmd = append(cmd, "--suite_args_json", string(bytes))
	}
	return cmd, nil
}

func asSlices(cmd []string, timeout time.Duration) []*swarming.SwarmingRpcsTaskSlice {
	slices := make([]*swarming.SwarmingRpcsTaskSlice, 1)
	timeoutSecs := int64(timeout.Seconds() + 10*60)
	slices[0] = &swarming.SwarmingRpcsTaskSlice{
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command: cmd,
			Dimensions: []*swarming.SwarmingRpcsStringPair{
				{Key: "pool", Value: "default"},
			},
			ExecutionTimeoutSecs: timeoutSecs,
			// TODO(akeshet): Add additional necessary properties, such as
			// priority etc.
		},
		ExpirationSecs: timeoutSecs,
	}
	return slices
}
