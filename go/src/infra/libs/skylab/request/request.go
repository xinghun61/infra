// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package request provides a library to create swarming requests based on
// skylab test or task parameters.
package request

import (
	"fmt"
	"strings"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/worker"
)

// Args defines the set of arguments for creating a request.
type Args struct {
	Cmd                     worker.Command
	Tags                    []string
	ProvisionableDimensions []string
	Dimensions              []string
	TimeoutMins             int
	Priority                int64
	ParentTaskID            string
}

// New creates a new swarming request for the given worker command and parameters.
func New(args Args) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	slices, err := getSlices(args.Cmd, args.ProvisionableDimensions, args.Dimensions, args.TimeoutMins)
	if err != nil {
		return nil, errors.Annotate(err, "create request").Err()
	}

	req := &swarming.SwarmingRpcsNewTaskRequest{
		Name:         args.Cmd.TaskName,
		Tags:         args.Tags,
		TaskSlices:   slices,
		Priority:     args.Priority,
		ParentTaskId: args.ParentTaskID,
	}
	return req, nil
}

// getSlices generates and returns the set of swarming task slices for the given test task.
func getSlices(cmd worker.Command, provisionableDimensions []string, dimensions []string, timeoutMins int) ([]*swarming.SwarmingRpcsTaskSlice, error) {
	slices := make([]*swarming.SwarmingRpcsTaskSlice, 1, 2)

	basePairs, err := toPairs(dimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}
	provisionablePairs, err := toPairs(provisionableDimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}

	s0Dims := append(basePairs, provisionablePairs...)
	slices[0] = taskSlice(cmd.Args(), s0Dims, timeoutMins)

	if len(provisionableDimensions) != 0 {
		cmd.ProvisionLabels = provisionDimensionsToLabels(provisionableDimensions)
		s1Dims := basePairs
		slices = append(slices, taskSlice(cmd.Args(), s1Dims, timeoutMins))
	}

	finalSlice := slices[len(slices)-1]
	finalSlice.ExpirationSecs = int64(timeoutMins * 60)

	return slices, nil
}

func taskSlice(command []string, dimensions []*swarming.SwarmingRpcsStringPair, timeoutMins int) *swarming.SwarmingRpcsTaskSlice {
	return &swarming.SwarmingRpcsTaskSlice{
		// We want all slices to wait, at least a little while, for bots with
		// metching dimensions.
		// For slice 0: This allows the task to try to re-use provisionable
		// labels that get set by previous tasks with the same label that are
		// about to finish.
		// For slice 1: This allows the task to wait for devices to get
		// repaired, if there are no devices with dut_state:ready.
		WaitForCapacity: true,
		// Slice 0 should have a fairly short expiration time, to reduce
		// overhead for tasks that are the first ones enqueue with a particular
		// provisionable label. This value will be overwritten for the final
		// slice of a task.
		ExpirationSecs: 30,
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command:              command,
			Dimensions:           dimensions,
			ExecutionTimeoutSecs: int64(timeoutMins * 60),
		},
	}
}

// provisionDimensionsToLabels converts provisionable dimensions to labels.
func provisionDimensionsToLabels(dims []string) []string {
	labels := make([]string, len(dims))
	for i, l := range dims {
		labels[i] = strings.TrimPrefix(l, "provisionable-")
	}
	return labels
}

// toPairs converts a slice of strings in foo:bar form to a slice of swarming
// rpc string pairs.
func toPairs(dimensions []string) ([]*swarming.SwarmingRpcsStringPair, error) {
	pairs := make([]*swarming.SwarmingRpcsStringPair, len(dimensions))
	for i, d := range dimensions {
		k, v := strpair.Parse(d)
		if v == "" {
			return nil, fmt.Errorf("malformed dimension with key '%s' has no value", k)
		}
		pairs[i] = &swarming.SwarmingRpcsStringPair{Key: k, Value: v}
	}
	return pairs, nil
}
