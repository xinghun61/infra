// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strconv"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/bb"
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
		c.createRunCommon.Register(&c.Flags)
		c.Flags.IntVar(&c.maxRetries, "max-retries", 0,
			`Maximum retries allowed in total for all child tests of this
suite. No retry if it is 0.`)
		// TODO(akeshet): Deprecate this arg; it will be irrelevant in the cros_test_platform
		// recipe, and is problematic even in the swarming suite bot implementation
		// (because of a latent swarming feature that cancels child tasks once
		// parent task is killed).
		c.Flags.BoolVar(&c.orphan, "orphan", false, "Create a suite that doesn't wait for its child tests to finish. Internal or expert use ONLY!")
		c.Flags.BoolVar(&c.json, "json", false, "Format output as JSON")
		c.Flags.StringVar(&c.taskName, "task-name", "", "Optional name to be used for the Swarming task.")
		return c
	},
}

type createSuiteRun struct {
	subcommands.CommandRunBase
	createRunCommon
	authFlags  authcli.Flags
	envFlags   envFlags
	maxRetries int
	orphan     bool
	json       bool
	taskName   string
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
	suiteName := c.Flags.Arg(0)

	if c.buildBucket {
		return c.innerRunBB(ctx, a, suiteName)
	}
	return c.innerRunSwarming(ctx, a, suiteName)

}

func (c *createSuiteRun) validateArgs() error {
	if err := c.createRunCommon.ValidateArgs(c.Flags); err != nil {
		return err
	}

	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing suite name")
	}

	return nil
}

func (c *createSuiteRun) innerRunBB(ctx context.Context, a subcommands.Application, suiteName string) error {
	if err := c.validateForBB(); err != nil {
		return err
	}

	client, err := bb.NewClient(ctx, c.envFlags.Env(), c.authFlags)
	if err != nil {
		return err
	}

	recipeArg, err := c.RecipeArgs()
	if err != nil {
		return err
	}
	recipeArg.TestPlan = recipe.NewTestPlanForSuites(suiteName)
	buildID, err := client.ScheduleBuild(ctx, recipeArg.TestPlatformRequest(), c.buildTags(suiteName))
	if err != nil {
		return err
	}
	buildURL := client.BuildURL(buildID)
	if c.json {
		return printScheduledTaskJSON(a.GetOut(), "cros_test_platform", fmt.Sprintf("%d", buildID), buildURL)
	}
	fmt.Fprintf(a.GetOut(), "Created request at %s\n", buildURL)
	return nil
}

func (c *createSuiteRun) validateForBB() error {
	// TODO(akeshet): support for all of these arguments, or deprecate them.
	if c.orphan {
		return errors.Reason("orphan not supported in -bb mode").Err()
	}
	return nil
}

func (c *createSuiteRun) innerRunSwarming(ctx context.Context, a subcommands.Application, suiteName string) error {
	e := c.envFlags.Env()
	dimensions := []string{"pool:ChromeOSSkylab-suite"}
	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}
	slices, err := getSuiteSlices(c.board, c.model, c.pool, c.image, suiteName, c.qsAccount, c.priority, c.timeoutMins, c.maxRetries, dimensions, keyvals, c.orphan)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}

	h, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, e.SwarmingService)
	if err != nil {
		return errors.Annotate(err, "failed to create client").Err()
	}

	taskName := c.taskName
	if taskName == "" {
		taskName = c.image + "-" + suiteName
	}
	tags := append(c.buildTags(suiteName), "luci_project:"+e.LUCIProject)
	taskID, err := createSuiteTask(ctx, client, taskName, c.priority, slices, tags)
	if err != nil {
		return errors.Annotate(err, "create suite").Err()
	}
	taskURL := swarming.TaskURL(e.SwarmingService, taskID)
	if c.json {
		_ = printScheduledTaskJSON(a.GetOut(), taskName, taskID, taskURL)
	}
	fmt.Fprintf(a.GetOut(), "Created Swarming Suite task %s\n", taskURL)
	return nil
}

func (c *createSuiteRun) buildTags(suiteName string) []string {
	return append(c.createRunCommon.BuildTags(), "skylab-tool:create-suite", fmt.Sprintf("suite:%s", suiteName))
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

func printScheduledTaskJSON(w io.Writer, name string, ID string, URL string) error {
	t := struct {
		Name string `json:"task_name"`
		ID   string `json:"task_id"`
		URL  string `json:"task_url"`
	}{
		Name: name,
		ID:   ID,
		URL:  URL,
	}
	return json.NewEncoder(w).Encode(t)
}
