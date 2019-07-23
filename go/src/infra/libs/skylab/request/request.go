// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package request provides a library to create swarming requests based on
// skylab test or task parameters.
package request

import (
	"fmt"
	"strings"
	"time"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/inventory"
	swarming_inventory "infra/libs/skylab/inventory/swarming"
	"infra/libs/skylab/worker"
)

// Args defines the set of arguments for creating a request.
type Args struct {
	// Cmd specifies the payload command to run for the request.
	Cmd          worker.Command
	SwarmingTags []string
	// ProvisionableDimensions specifies the provisionable dimensions in raw
	// string form; e.g. {"provisionable-cros-version:foo-cq-R75-1.2.3.4"}
	ProvisionableDimensions []string
	// Dimensions specifies swarming dimensions in raw string form.
	//
	// It is preferable to specify dimensions via the SchedulableLabels
	// argument. This argument should only be used for user-supplied freeform
	// dimensions; e.g. {"label-power:battery"}
	//
	// TODO(akeshet): This feature is needed to support `skylab create-test`
	// which allows arbitrary user-specified dimensions. If and when that
	// feature is dropped, then this feature can be dropped as well.
	Dimensions []string
	// SchedulableLabels specifies schedulable label requirements that will
	// be translated to dimensions.
	SchedulableLabels inventory.SchedulableLabels
	Timeout           time.Duration
	Priority          int64
	ParentTaskID      string
}

// New creates a new swarming request for the given worker command and parameters.
func New(args Args) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	slices, err := getSlices(args.Cmd, args.ProvisionableDimensions, args.Dimensions, args.SchedulableLabels, args.Timeout)
	if err != nil {
		return nil, errors.Annotate(err, "create request").Err()
	}

	req := &swarming.SwarmingRpcsNewTaskRequest{
		Name:         args.Cmd.TaskName,
		Tags:         args.SwarmingTags,
		TaskSlices:   slices,
		Priority:     args.Priority,
		ParentTaskId: args.ParentTaskID,
	}
	return req, nil
}

// getSlices generates and returns the set of swarming task slices for the given test task.
func getSlices(cmd worker.Command, provisionableDimensions []string, dimensions []string, inv inventory.SchedulableLabels, timeout time.Duration) ([]*swarming.SwarmingRpcsTaskSlice, error) {
	slices := make([]*swarming.SwarmingRpcsTaskSlice, 1, 2)

	// TODO(crbug.com/939976): Generalize request library to support non-test tasks.
	basePairs, _ := stringToPairs("pool:ChromeOSSkylab", "dut_state:ready")

	rawPairs, err := stringToPairs(dimensions...)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}

	inventoryPairs := schedulableLabelsToPairs(inv)

	basePairs = append(basePairs, inventoryPairs...)
	basePairs = append(basePairs, rawPairs...)

	provisionablePairs, err := stringToPairs(provisionableDimensions...)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}

	s0Dims := append(basePairs, provisionablePairs...)
	slices[0] = taskSlice(cmd.Args(), s0Dims, timeout)

	if len(provisionableDimensions) != 0 {
		cmd.ProvisionLabels = provisionDimensionsToLabels(provisionableDimensions)
		s1Dims := basePairs
		slices = append(slices, taskSlice(cmd.Args(), s1Dims, timeout))
	}

	finalSlice := slices[len(slices)-1]
	finalSlice.ExpirationSecs = int64(timeout.Seconds())

	return slices, nil
}

func taskSlice(command []string, dimensions []*swarming.SwarmingRpcsStringPair, timeout time.Duration) *swarming.SwarmingRpcsTaskSlice {
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
			ExecutionTimeoutSecs: int64(timeout.Seconds()),
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

// stringToPairs converts a slice of strings in foo:bar form to a slice of swarming
// rpc string pairs.
func stringToPairs(dimensions ...string) ([]*swarming.SwarmingRpcsStringPair, error) {
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

func schedulableLabelsToPairs(inv inventory.SchedulableLabels) []*swarming.SwarmingRpcsStringPair {
	dimensions := swarming_inventory.Convert(&inv)
	pairs := make([]*swarming.SwarmingRpcsStringPair, 0, len(dimensions))
	for key, values := range dimensions {
		for _, value := range values {
			pairs = append(pairs, &swarming.SwarmingRpcsStringPair{Key: key, Value: value})
		}
	}
	return pairs
}
