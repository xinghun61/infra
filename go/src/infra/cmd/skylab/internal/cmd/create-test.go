// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/swarming"
	"infra/libs/skylab/worker"
)

// CreateTest subcommand: create a test task.
var CreateTest = &subcommands.Command{
	UsageLine: `create-test [FLAGS...] TEST_NAME [DIMENSION_KEY:VALUE...]`,
	ShortDesc: "create a test task",
	LongDesc: `Create a test task.

You must supply -pool, -image, and one of -board or -model.

This command does not wait for the task to start running.`,
	CommandRun: func() subcommands.CommandRun {
		c := &createTestRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.client, "client-test", false, "Task is a client-side test.")
		c.Flags.StringVar(&c.image, "image", "",
			`Fully specified image name to run test against,
e.g., reef-canary/R73-11580.0.0.`)
		c.Flags.StringVar(&c.board, "board", "", "Board to run test on.")
		c.Flags.StringVar(&c.model, "model", "", "Model to run test on.")
		// TODO(akeshet): Decide on whether these should be specified in their proto
		// format (e.g. DUT_POOL_BVT) or in a human readable format, e.g. bvt. Provide a
		// list of common choices.
		c.Flags.StringVar(&c.pool, "pool", "", "Device pool to run test on.")
		c.Flags.IntVar(&c.priority, "priority", defaultTaskPriority,
			`Specify the priority of the test.  A high value means this test
will be executed in a low priority. If the tasks runs in a quotascheduler controlled pool, this value will be ignored.`)
		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", 30, "Task runtime timeout.")
		c.Flags.Var(flag.StringSlice(&c.tags), "tag", "Swarming tag for test; may be specified multiple times.")
		c.Flags.Var(flag.StringSlice(&c.keyvals), "keyval",
			`Autotest keyval for test.  May be specified multiple times.`)
		c.Flags.StringVar(&c.testArgs, "test-args", "", "Test arguments string (meaning depends on test).")
		c.Flags.StringVar(&c.qsAccount, "qs-account", "", "Quota Scheduler account to use for this task.  Optional.")
		c.Flags.Var(flag.StringSlice(&c.provisionLabels), "provision-label",
			`Additional provisionable labels to use for the test
(e.g. cheets-version:git_pi-arc/cheets_x86_64).  May be specified
multiple times.  Optional.`)
		c.Flags.StringVar(&c.parentTaskID, "parent-task-run-id", "", "For internal use only. Task run ID of the parent (suite) task to this test. Note that this must be a run ID (i.e. not ending in 0).")
		return c
	},
}

type createTestRun struct {
	subcommands.CommandRunBase
	authFlags       authcli.Flags
	envFlags        envFlags
	client          bool
	image           string
	board           string
	model           string
	pool            string
	priority        int
	timeoutMins     int
	tags            []string
	keyvals         []string
	testArgs        string
	qsAccount       string
	provisionLabels []string
	parentTaskID    string
}

// validateArgs ensures that the command line arguments are
func (c *createTestRun) validateArgs() error {
	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing test name")
	}

	if c.board == "" && c.model == "" {
		return NewUsageError(c.Flags, "missing -board or a -model")
	}

	if c.pool == "" {
		return NewUsageError(c.Flags, "missing -pool")
	}

	if c.image == "" {
		return NewUsageError(c.Flags, "missing -image")
	}

	if c.priority < 50 || c.priority > 255 {
		return NewUsageError(c.Flags, "priority should in [50,255]")
	}
	return nil
}

func (c *createTestRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *createTestRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
	}

	taskName := c.Flags.Arg(0)
	userDimensions := c.Flags.Args()[1:]

	dimensions := []string{"pool:ChromeOSSkylab", "dut_state:ready"}
	if c.board != "" {
		dimensions = append(dimensions, "label-board:"+c.board)
	}
	if c.model != "" {
		dimensions = append(dimensions, "label-model:"+c.model)
	}
	if c.pool != "" {
		dimensions = append(dimensions, "label-pool:"+c.pool)
	}

	dimensions = append(dimensions, userDimensions...)

	var provisionableLabels []string
	if c.image != "" {
		provisionableLabels = append(provisionableLabels, "provisionable-cros-version:"+c.image)
	}
	for _, p := range c.provisionLabels {
		provisionableLabels = append(provisionableLabels, "provisionable-"+p)
	}

	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}

	e := c.envFlags.Env()

	cmd := worker.Command{
		TaskName:   taskName,
		ClientTest: c.client,
		Keyvals:    keyvals,
		TestArgs:   c.testArgs,
	}
	cmd.Config(worker.Env(e.Wrapped()))
	slices, err := getSlices(cmd, provisionableLabels, dimensions, c.timeoutMins)
	if err != nil {
		return errors.Annotate(err, "create test").Err()
	}

	tags := append(c.tags, "skylab-tool:create-test", "log_location:"+cmd.LogDogAnnotationURL, "luci_project:"+e.LUCIProject)
	if c.qsAccount != "" {
		tags = append(tags, "qs_account:"+c.qsAccount)
	}

	req := &swarming_api.SwarmingRpcsNewTaskRequest{
		Name:         taskName,
		Tags:         tags,
		TaskSlices:   slices,
		Priority:     int64(c.priority),
		ParentTaskId: c.parentTaskID,
	}

	ctx := cli.GetContext(a, c, env)
	h, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, e.SwarmingService)
	if err != nil {
		return err
	}

	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	resp, err := client.CreateTask(ctx, req)
	if err != nil {
		return errors.Annotate(err, "create test").Err()
	}

	fmt.Fprintf(a.GetOut(), "Created Swarming task %s\n", swarmingTaskURL(e, resp.TaskId))
	return nil
}

func taskSlice(command []string, dimensions []*swarming_api.SwarmingRpcsStringPair, timeoutMins int) *swarming_api.SwarmingRpcsTaskSlice {
	return &swarming_api.SwarmingRpcsTaskSlice{
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
		Properties: &swarming_api.SwarmingRpcsTaskProperties{
			Command:              command,
			Dimensions:           dimensions,
			ExecutionTimeoutSecs: int64(timeoutMins * 60),
		},
	}
}

// getSlices generates and returns the set of swarming task slices for the given test task.
func getSlices(cmd worker.Command, provisionableDimensions []string, dimensions []string, timeoutMins int) ([]*swarming_api.SwarmingRpcsTaskSlice, error) {
	slices := make([]*swarming_api.SwarmingRpcsTaskSlice, 1, 2)

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

	// Note: This is the common case.
	if len(provisionableDimensions) != 0 {
		// Make a copy before mutating.
		cmd := cmd
		cmd.ProvisionLabels = provisionDimensionsToLabels(provisionableDimensions)
		s1Dims := basePairs
		slices = append(slices, taskSlice(cmd.Args(), s1Dims, timeoutMins))
	}

	finalSlice := slices[len(slices)-1]
	// TODO(akeshet): Determine the correct expiration time, or make it a
	// commandline argument.
	finalSlice.ExpirationSecs = int64(timeoutMins * 60)

	return slices, nil
}

// provisionDimensionsToLabels converts provisionable dimensions to labels.
func provisionDimensionsToLabels(dims []string) []string {
	labels := make([]string, len(dims))
	for i, l := range dims {
		labels[i] = strings.TrimPrefix(l, "provisionable-")
	}
	return labels
}
