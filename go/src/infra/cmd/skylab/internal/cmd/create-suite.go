// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/cmd/recipe"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/swarming"
)

// CreateSuite subcommand: create a suite task.
var CreateSuite = &subcommands.Command{
	UsageLine: "create-suite [FLAGS...] SUITE_NAME",
	ShortDesc: "create a suite task",
	LongDesc:  "Create a suite task, with the given suite name.",
	CommandRun: func() subcommands.CommandRun {
		c := &createSuiteRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.StringVar(&c.board, "board", "", "Board to run suite on.")
		c.Flags.StringVar(&c.model, "model", "", "Model to run suite on.")
		c.Flags.StringVar(&c.pool, "pool", "", "Device pool to run suite on.")
		c.Flags.StringVar(&c.image, "image", "", "Fully specified image name to run suite against, e.g. reef-canary/R73-11580.0.0")
		c.Flags.IntVar(&c.priority, "priority", defaultTaskPriority,
			`Specify the priority of the suite.  A high value means this suite
will be executed in a low priority.`)
		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", 20,
			`Time (counting from when the task starts) after which task will be
killed if it hasn't completed.`)
		c.Flags.IntVar(&c.maxRetries, "max-retries", 0,
			`Maximum retries allowed in total for all child tests of this
suite. No retry if it is 0.`)
		c.Flags.Var(flag.StringSlice(&c.tags), "tag", "Swarming tag for suite; may be specified multiple times.")
		c.Flags.Var(flag.StringSlice(&c.keyvals), "keyval",
			`Autotest keyval for test. Key may not contain : character. May be
specified multiple times.`)
		c.Flags.StringVar(&c.qsAccount, "qs-account", "", "Quotascheduler account for test jobs.")
		// TODO(akeshet): Deprecate this arg; it will be irrelevant in the cros_test_platform
		// recipe, and is problematic even in the swarming suite bot implementation
		// (because of a latent swarming feature that cancels child tasks once
		// parent task is killed).
		c.Flags.BoolVar(&c.orphan, "orphan", false, "Create a suite that doesn't wait for its child tests to finish. Internal or expert use ONLY!")
		c.Flags.BoolVar(&c.json, "json", false, "Format output as JSON")
		c.Flags.StringVar(&c.taskName, "task-name", "", "Optional name to be used for the Swarming task.")
		c.Flags.BoolVar(&c.buildBucket, "bb", false, "(Expert use only, not a stable API) use buildbucket recipe backend.")
		return c
	},
}

type createSuiteRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	envFlags    envFlags
	board       string
	model       string
	pool        string
	image       string
	priority    int
	timeoutMins int
	maxRetries  int
	tags        []string
	keyvals     []string
	qsAccount   string
	orphan      bool
	json        bool
	taskName    string
	buildBucket bool
}

func (c *createSuiteRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *createSuiteRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)
	e := c.envFlags.Env()
	suiteName := c.Flags.Arg(0)

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
			SuiteNames:   []string{suiteName},
			Timeout:      time.Duration(c.timeoutMins) * time.Minute,
		}

		return buildbucketRun(ctx, args, e, c.authFlags)
	}

	dimensions := []string{"pool:ChromeOSSkylab-suite"}
	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}
	slices, err := getSuiteSlices(c.board, c.model, c.pool, c.image, suiteName, c.qsAccount, c.priority, c.timeoutMins, c.maxRetries, dimensions, keyvals, c.orphan)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}

	tags := append(c.tags,
		"skylab-tool:create-suite",
		"luci_project:"+e.LUCIProject,
		"build:"+c.image,
		"suite:"+suiteName,
		"label-board:"+c.board,
		"label-model:"+c.model,
		"label-pool:"+c.pool,
		"priority:"+strconv.Itoa(c.priority))

	h, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, e.SwarmingService)
	if err != nil {
		return errors.Annotate(err, "failed to create client").Err()
	}

	task := taskInfo{
		Name: c.image + "-" + suiteName,
	}
	if c.taskName != "" {
		task.Name = c.taskName
	}

	task.ID, err = createSuiteTask(ctx, client, task.Name, c.priority, slices, tags)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}

	task.URL = swarming.TaskURL(e.SwarmingService, task.ID)
	if c.json {
		return json.NewEncoder(a.GetOut()).Encode(task)
	}

	fmt.Fprintf(a.GetOut(), "Created Swarming Suite task %s\n", task.URL)
	return nil
}

func (c *createSuiteRun) validateArgs() error {
	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing suite name")
	}

	if c.board == "" {
		return NewUsageError(c.Flags, "missing -board")
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

func (c *createSuiteRun) validateForBB() error {
	// TODO(akeshet): support for all of these arguments, or deprecate them.
	if len(c.keyvals) > 0 {
		return errors.Reason("keyvals not yet supported in -bb mode").Err()
	}
	if len(c.tags) > 0 {
		return errors.Reason("tags not yet supported in -bb mode").Err()
	}
	if c.priority != defaultTaskPriority {
		return errors.Reason("nondefault priority not yet supported in -bb mode").Err()
	}
	if c.maxRetries != 0 {
		return errors.Reason("retries not yet supported in -bb mode").Err()
	}
	if c.orphan {
		return errors.Reason("orphan not supported in -bb mode").Err()
	}
	return nil
}

func newTaskSlice(command []string, dimensions []*swarming_api.SwarmingRpcsStringPair, timeoutMins int) *swarming_api.SwarmingRpcsTaskSlice {
	return &swarming_api.SwarmingRpcsTaskSlice{
		ExpirationSecs:  300,
		WaitForCapacity: false,
		Properties: &swarming_api.SwarmingRpcsTaskProperties{
			Command:              command,
			Dimensions:           dimensions,
			ExecutionTimeoutSecs: int64(timeoutMins * 60),
		},
	}
}

func getSuiteSlices(board string, model string, pool string, image string, suiteName string, qsAccount string, priority int, timeoutMins int, maxRetries int, dimensions []string, keyvals map[string]string, orphan bool) ([]*swarming_api.SwarmingRpcsTaskSlice, error) {
	dims, err := toPairs(dimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}
	cmd := getRunSuiteCmd(board, model, pool, image, suiteName, qsAccount, priority, timeoutMins, maxRetries, keyvals, orphan)
	return []*swarming_api.SwarmingRpcsTaskSlice{newTaskSlice(cmd, dims, timeoutMins)}, nil
}

func getRunSuiteCmd(board string, model string, pool string, image string, suiteName string, qsAccount string, priority int, timeoutMins int, maxRetries int, keyvals map[string]string, orphan bool) []string {
	cmd := []string{
		"/usr/local/autotest/bin/run_suite_skylab",
		"--build", image,
		"--board", board,
		"--pool", pool,
		"--suite_name", suiteName,
		"--priority", strconv.Itoa(priority),
		"--timeout_mins", strconv.Itoa(timeoutMins)}

	if orphan {
		cmd = append(cmd, "--create_and_return")
	}

	if model != "" {
		cmd = append(cmd, "--model", model)
	}
	if qsAccount != "" {
		cmd = append(cmd, "--quota_account", qsAccount)
	}
	if maxRetries > 0 {
		cmd = append(cmd, "--test_retry")
		cmd = append(cmd, "--max_retries", strconv.Itoa(maxRetries))
	}
	if len(keyvals) > 0 {
		keyvalsJSON, err := json.Marshal(keyvals)
		if err != nil {
			panic(err)
		}
		cmd = append(cmd, "--job_keyvals", string(keyvalsJSON))
	}
	return cmd
}

func createSuiteTask(ctx context.Context, t *swarming.Client, taskName string, priority int, slices []*swarming_api.SwarmingRpcsTaskSlice, tags []string) (taskID string, err error) {
	req := &swarming_api.SwarmingRpcsNewTaskRequest{
		Name:       taskName,
		Tags:       tags,
		TaskSlices: slices,
		Priority:   int64(priority),
	}
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	resp, err := t.CreateTask(ctx, req)
	if err != nil {
		return "", errors.Annotate(err, "create suite").Err()
	}

	return resp.TaskId, nil
}
