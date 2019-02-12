// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/flagx"
	"infra/cmd/skylab/internal/site"
)

// CreateSuite subcommand: create a suite task.
var CreateSuite = &subcommands.Command{
	UsageLine: "create-suite [FLAGS...] SUITE_NAME",
	ShortDesc: "create a suite task",
	LongDesc: `Create a suite task, with the given suite name.

You must supply -pool and -image.

This command does not wait for the task to start running.`,
	CommandRun: func() subcommands.CommandRun {
		c := &createSuiteRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.StringVar(&c.board, "board", "", "Board to run suite on.")
		c.Flags.StringVar(&c.model, "model", "", "Model to run suite on.")
		c.Flags.StringVar(&c.pool, "pool", "", "Device pool to run suite on.")
		c.Flags.StringVar(&c.image, "image", "", "Fully specified image name to run suite against, e.g. reef-canary/R73-11580.0.0")
		c.Flags.Var(flagx.NewChoice(&c.priority, sortedPriorityKeys()...), "priority",
			`Specify the priority of the suite.  A high value means this suite
will be executed in a low priority.  It should one of:
`+strings.Join(sortedPriorityKeys(), ", "))
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
	priority    string
	timeoutMins int
	maxRetries  int
	tags        []string
	keyvals     []string
	qsAccount   string
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

	dimensions := []string{"pool:ChromeOSSkylab-suite"}
	if c.priority == "" {
		c.priority = defaultTaskPriorityKey
	}
	priority := taskPriorityMap[c.priority]
	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}
	slices, err := getSuiteSlices(c.board, c.model, c.pool, c.image, suiteName, c.qsAccount, priority, c.timeoutMins, c.maxRetries, dimensions, keyvals)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}

	tags := append(c.tags,
		"skylab-tool:create-suite",
		"luci_project:"+e.LUCIProject,
		"build:"+c.image,
		"suite:"+suiteName)

	s, err := newSwarmingService(ctx, c.authFlags, e)
	if err != nil {
		return errors.Annotate(err, "failed to create Swarming client").Err()
	}

	taskName := c.image + "-" + suiteName
	taskID, err := createSuiteTask(ctx, s, taskName, priority, slices, tags)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}
	fmt.Fprintf(a.GetOut(), "Created Swarming task %s\n", swarmingTaskURL(e, taskID))
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

	return nil
}

func newTaskSlice(command []string, dimensions []*swarming.SwarmingRpcsStringPair, timeoutMins int) *swarming.SwarmingRpcsTaskSlice {
	return &swarming.SwarmingRpcsTaskSlice{
		ExpirationSecs:  300,
		WaitForCapacity: false,
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command:              command,
			Dimensions:           dimensions,
			ExecutionTimeoutSecs: int64(timeoutMins * 60),
		},
	}
}

func getSuiteSlices(board string, model string, pool string, image string, suiteName string, qsAccount string, priority int, timeoutMins int, maxRetries int, dimensions []string, keyvals map[string]string) ([]*swarming.SwarmingRpcsTaskSlice, error) {
	dims, err := toPairs(dimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}
	cmd := getRunSuiteCmd(board, model, pool, image, suiteName, qsAccount, priority, timeoutMins, maxRetries, keyvals)
	return []*swarming.SwarmingRpcsTaskSlice{newTaskSlice(cmd, dims, timeoutMins)}, nil
}

func getRunSuiteCmd(board string, model string, pool string, image string, suiteName string, qsAccount string, priority int, timeoutMins int, maxRetries int, keyvals map[string]string) []string {
	cmd := []string{
		"/usr/local/autotest/bin/run_suite_skylab",
		"--build", image,
		"--board", board,
		"--pool", pool,
		"--suite_name", suiteName,
		"--priority", strconv.Itoa(priority),
		"--timeout_mins", strconv.Itoa(timeoutMins),
		// By default the script creates the suite and return immediately, to avoid task timeout.
		"--create_and_return"}
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

func createSuiteTask(ctx context.Context, s *swarming.Service, taskName string, priority int, slices []*swarming.SwarmingRpcsTaskSlice, tags []string) (taskID string, err error) {
	req := newTaskRequest(taskName, tags, slices, int64(priority))
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	resp, err := s.Tasks.New(req).Context(ctx).Do()
	if err != nil {
		return "", errors.Annotate(err, "create suite").Err()
	}

	return resp.TaskId, nil
}
