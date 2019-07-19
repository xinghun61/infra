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

	"infra/cmd/skylab/internal/cmd/recipe"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/request"
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
		// TODO(akeshet): Deprecate this argument once recipe migration is complete;
		// the recipe ignores this argument, and determines it independently during
		// test enumeration.
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
		c.Flags.BoolVar(&c.buildBucket, "bb", false, "(Expert use only, not a stable API) use buildbucket recipe backend.")
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
	buildBucket     bool
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

	ctx := cli.GetContext(a, c, env)
	e := c.envFlags.Env()

	taskName := c.Flags.Arg(0)

	if c.buildBucket {
		if err := c.validateForBB(); err != nil {
			return err
		}
		args := recipe.Args{
			Board:        c.board,
			Image:        c.image,
			Model:        c.model,
			Pool:         c.pool,
			QuotaAccount: c.qsAccount,
			TestNames:    []string{taskName},
			Timeout:      time.Duration(c.timeoutMins) * time.Minute,
		}
		return buildbucketRun(ctx, args, e, c.authFlags)
	}

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

	tags := append(c.tags, "skylab-tool:create-test", "log_location:"+cmd.LogDogAnnotationURL, "luci_project:"+e.LUCIProject)
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

	h, err := httpClient(ctx, &c.authFlags)
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

func (c *createTestRun) validateForBB() error {
	// TODO(akeshet): support for all of these arguments, or deprecate them.
	if len(c.keyvals) > 0 {
		return errors.Reason("keyvals not yet supported in -bb mode").Err()
	}
	if c.testArgs != "" {
		return errors.Reason("test args not yet supported in -bb mode").Err()
	}
	if len(c.tags) > 0 {
		return errors.Reason("tags not yet supported in -bb mode").Err()
	}
	if c.parentTaskID != "" {
		return errors.Reason("parent task id not yet supported in -bb mode").Err()
	}
	if c.priority != defaultTaskPriority {
		return errors.Reason("nondefault priority not yet supported in -bb mode").Err()
	}
	if len(c.provisionLabels) != 0 {
		return errors.Reason("freeform provisionable labels not yet supported in -bb mode").Err()
	}
	return nil
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
	userDimensions := c.Flags.Args()[1:]
	return userDimensions
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
