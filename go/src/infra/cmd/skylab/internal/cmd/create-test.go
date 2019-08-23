// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/bb"
	"infra/cmd/skylab/internal/cmd/recipe"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/request"
	"infra/libs/skylab/swarming"
	"infra/libs/skylab/worker"
)

// CreateTest subcommand: create a test task.
var CreateTest = &subcommands.Command{
	UsageLine: `create-test [FLAGS...] TEST_NAME [TEST_NAME...]`,
	ShortDesc: "create a test task",
	LongDesc: `Create a test task.

You must supply -pool, -image, and one of -board or -model.

This command does not wait for the task to start running.`,
	CommandRun: func() subcommands.CommandRun {
		c := &createTestRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.createRunCommon.Register(&c.Flags)
		// TODO(akeshet): Deprecate this argument once recipe migration is complete;
		// the recipe ignores this argument, and determines it independently during
		// test enumeration.
		c.Flags.BoolVar(&c.client, "client-test", false, "Task is a client-side test.")
		c.Flags.StringVar(&c.testArgs, "test-args", "", "Test arguments string (meaning depends on test).")
		// TODO(akeshet): Move this argument to createRunCommon, so it can be shared among create-* subcommands.
		c.Flags.Var(flag.StringSlice(&c.provisionLabels), "provision-label",
			`Additional provisionable labels to use for the test
(e.g. cheets-version:git_pi-arc/cheets_x86_64).  May be specified
multiple times.  Optional.`)
		c.Flags.StringVar(&c.parentTaskID, "parent-task-run-id", "", "For internal use only. Task run ID of the parent (suite) task to this test. Note that this must be a run ID (i.e. not ending in 0).")
		c.Flags.Var(flag.StringSlice(&c.dimensions), "dim", "Additional scheduling dimension to apply to tests, as a KEY:VALUE string; may be specified multiple times.")
		return c
	},
}

type createTestRun struct {
	subcommands.CommandRunBase
	createRunCommon
	authFlags       authcli.Flags
	envFlags        envFlags
	client          bool
	testArgs        string
	provisionLabels []string
	parentTaskID    string
	dimensions      []string
}

// validateArgs ensures that the command line arguments are
func (c *createTestRun) validateArgs() error {
	if err := c.createRunCommon.ValidateArgs(c.Flags); err != nil {
		return err
	}

	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing test name")
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

	if c.buildBucket {
		return c.innerRunBB(a, args, env)
	}
	return c.innerRunSwarming(a, args, env)
}

func (c *createTestRun) innerRunBB(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateForBB(); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)
	e := c.envFlags.Env()
	client, err := bb.NewClient(ctx, e, c.authFlags)
	if err != nil {
		return err
	}

	recipeArg, err := c.RecipeArgs()
	if err != nil {
		return err
	}
	recipeArg.TestPlan = recipe.NewTestPlanForAutotestTests(c.testArgs, args...)
	recipeArg.FreeformSwarmingDimensions = c.dimensions

	buildID, err := client.ScheduleBuild(ctx, recipeArg.TestPlatformRequest(), c.buildTags())
	if err != nil {
		return err
	}
	fmt.Fprintf(a.GetOut(), "Created request at %s\n", client.BuildURL(buildID))
	return nil
}

func (c *createTestRun) validateForBB() error {
	// TODO(akeshet): support for all of these arguments, or deprecate them.
	if c.parentTaskID != "" {
		return errors.Reason("parent task id not yet supported in -bb mode").Err()
	}
	if len(c.provisionLabels) != 0 {
		return errors.Reason("freeform provisionable labels not yet supported in -bb mode").Err()
	}
	return nil
}

func (c *createTestRun) innerRunSwarming(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	e := c.envFlags.Env()

	if c.Flags.NArg() > 1 {
		return errors.Reason("multiple tests in a single command only supported in -bb mode").Err()
	}

	taskName := c.Flags.Arg(0)

	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}

	cmd := worker.Command{
		TaskName:   taskName,
		ClientTest: c.client,
		Keyvals:    keyvals,
		TestArgs:   c.testArgs,
	}
	cmd.Config(e.Wrapped())

	tags := append(c.buildTags(), "log_location:"+cmd.LogDogAnnotationURL, "luci_project:"+e.LUCIProject)
	if c.qsAccount != "" {
		tags = append(tags, "qs_account:"+c.qsAccount)
	}

	ra := request.Args{
		Cmd:                     cmd,
		SwarmingTags:            tags,
		ProvisionableDimensions: c.getProvisionableDimensions(),
		Dimensions:              c.getDimensions(),
		SchedulableLabels:       c.getLabels(),
		Timeout:                 time.Duration(c.timeoutMins) * time.Minute,
		Priority:                int64(c.priority),
		ParentTaskID:            c.parentTaskID,
	}
	req, err := request.New(ra)

	h, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, e.SwarmingService)
	if err != nil {
		return err
	}

	ctx, cf := context.WithTimeout(ctx, 120*time.Second)
	defer cf()
	resp, err := client.CreateTask(ctx, req)
	if err != nil {
		if err == context.DeadlineExceeded {
			return errors.Reason("timed out while attempting to create swarming task").Err()
		}
		return errors.Annotate(err, "create test").Err()
	}

	fmt.Fprintf(a.GetOut(), "Created Swarming task %s\n", swarming.TaskURL(e.SwarmingService, resp.TaskId))
	return nil
}

func (c *createTestRun) buildTags() []string {
	return append(c.createRunCommon.BuildTags(), "skylab-tool:create-test")
}

func (c *createTestRun) getLabels() inventory.SchedulableLabels {
	labels := inventory.SchedulableLabels{}

	if c.board != "" {
		labels.Board = &c.board
	}
	if c.model != "" {
		labels.Model = &c.model
	}
	if c.pool != "" {
		pool, ok := inventory.SchedulableLabels_DUTPool_value[c.pool]
		if ok {
			labels.CriticalPools = []inventory.SchedulableLabels_DUTPool{inventory.SchedulableLabels_DUTPool(pool)}
		} else {
			labels.SelfServePools = []string{c.pool}
		}
	}
	return labels
}

func (c *createTestRun) getDimensions() []string {
	return c.dimensions
}

func (c *createTestRun) getProvisionableDimensions() []string {
	var provisionableDimensions []string
	if c.image != "" {
		provisionableDimensions = append(provisionableDimensions, "provisionable-cros-version:"+c.image)
	}
	for _, p := range c.provisionLabels {
		provisionableDimensions = append(provisionableDimensions, "provisionable-"+p)
	}
	return provisionableDimensions
}
