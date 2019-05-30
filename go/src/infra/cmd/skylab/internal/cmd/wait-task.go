// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"infra/cmd/skylab/internal/site"
	"io"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
)

// WaitTask subcommand: wait for a task to finish.
var WaitTask = &subcommands.Command{
	UsageLine: "wait-task [FLAGS...] SWARMING_TASK_ID",
	ShortDesc: "wait for a task to complete",
	LongDesc:  `Wait for the task with the given swarming task id to complete, and summarize its results.`,
	CommandRun: func() subcommands.CommandRun {
		c := &waitTaskRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", -1, "The maxinum number of minutes to wait for the task to finish. Default: no timeout.")
		return c
	},
}

type waitTaskRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	envFlags    envFlags
	timeoutMins int
}

type taskResult struct {
	Name  string `json:"name"`
	State string `json:"state"`
	// TODO(crbug.com/964573): Deprecate this field.
	Failure   bool   `json:"failure"`
	Success   bool   `json:"success"`
	TaskRunID string `json:"task-run-id"`
}

type waitTaskResult struct {
	TaskResult   *taskResult   `json:"task-result"`
	Stdout       string        `json:"stdout"`
	ChildResults []*taskResult `json:"child-results"`
}

func (c *waitTaskRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *waitTaskRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	taskID := c.Flags.Arg(0)
	if taskID == "" {
		return NewUsageError(c.Flags, "missing swarming task ID")
	}

	siteEnv := c.envFlags.Env()
	ctx := cli.GetContext(a, c, env)
	s, err := newSwarmingService(ctx, c.authFlags, siteEnv)
	if err != nil {
		return err
	}

	var taskWaitCtx context.Context
	var taskWaitCancel context.CancelFunc
	if c.timeoutMins >= 0 {
		taskWaitCtx, taskWaitCancel = context.WithTimeout(ctx, time.Duration(c.timeoutMins)*time.Minute)
	} else {
		taskWaitCtx, taskWaitCancel = context.WithCancel(ctx)
	}
	defer taskWaitCancel()

	if err = waitTask(taskWaitCtx, taskID, s); err != nil {
		if err == context.DeadlineExceeded {
			return errors.New("timed out waiting for task to complete")
		}
		return err
	}

	return postWaitTask(ctx, taskID, s, a.GetOut())
}

// waitTask waits until the task with the given ID has completed.
//
// It returns an error if the given context was cancelled or in case of swarming
// rpc failures (after transient retry).
func waitTask(ctx context.Context, taskID string, s *swarming.Service) error {
	sleepInterval := time.Duration(15 * time.Second)
	for {
		results, err := getSwarmingResultsForIds(ctx, []string{taskID}, s)
		if err != nil {
			return err
		}
		// Possible values:
		//   "BOT_DIED"
		//   "CANCELED"
		//   "COMPLETED"
		//   "EXPIRED"
		//   "INVALID"
		//   "KILLED"
		//   "NO_RESOURCE"
		//   "PENDING"
		//   "RUNNING"
		//   "TIMED_OUT"
		// Keep waiting if task state is RUNNING or PENDING
		if s := results[0].State; s != "RUNNING" && s != "PENDING" {
			return nil
		}
		if err = sleepOrCancel(ctx, sleepInterval); err != nil {
			return err
		}
	}
}

func sleepOrCancel(ctx context.Context, duration time.Duration) error {
	sleepTimer := time.NewTimer(duration)
	select {
	case <-sleepTimer.C:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func getSwarmingStdoutsForIds(ctx context.Context, IDs []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskOutput, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results := make([]*swarming.SwarmingRpcsTaskOutput, len(IDs))
	for i, ID := range IDs {
		var result *swarming.SwarmingRpcsTaskOutput
		getResult := func() error {
			var err error
			result, err = s.Task.Stdout(ID).Context(ctx).Do()
			return err
		}
		if err := swarmingCallWithRetries(ctx, getResult); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("get swarming stdout for task %s", ID)).Err()
		}
		results[i] = result
	}
	return results, nil
}

func asTaskResult(s *swarming.SwarmingRpcsTaskResult) *taskResult {
	return &taskResult{
		Name:  s.Name,
		State: s.State,
		// TODO(crbug.com/964573): Deprecate this field.
		Failure:   s.Failure,
		Success:   !s.Failure && (s.State == "COMPLETED" || s.State == "COMPLETED_SUCCESS"),
		TaskRunID: s.RunId,
	}
}

func postWaitTask(ctx context.Context, taskID string, s *swarming.Service, w io.Writer) error {
	results, err := getSwarmingResultsForIds(ctx, []string{taskID}, s)
	if err != nil {
		return err
	}
	stdouts, err := getSwarmingStdoutsForIds(ctx, []string{taskID}, s)
	if err != nil {
		return err
	}
	childs, err := getSwarmingResultsForIds(ctx, results[0].ChildrenTaskIds, s)
	if err != nil {
		return err
	}
	childResults := make([]*taskResult, len(childs))
	for i, c := range childs {
		childResults[i] = asTaskResult(c)
	}
	tr := asTaskResult(results[0])
	result := &waitTaskResult{
		TaskResult:   tr,
		Stdout:       stdouts[0].Output,
		ChildResults: childResults,
	}
	printJSONResults(w, result)
	return nil
}

func printJSONResults(w io.Writer, m *waitTaskResult) {
	outputJSON, err := json.Marshal(m)
	if err != nil {
		panic(err)
	}
	fmt.Fprintf(w, string(outputJSON))
}
