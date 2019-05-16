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

		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", 20, "The maxinum number of minutes to wait for the task to finish.")
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
	Name    string `json:"name"`
	State   string `json:"state"`
	Failure bool   `json:"failure"`
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

	taskWaitCtx, taskWaitCancel := context.WithCancel(ctx)
	defer taskWaitCancel()
	taskWaitErr := make(chan error, 1)
	go waitTask(taskWaitCtx, taskWaitErr, taskID, s, a.GetErr())

	select {
	case err := <-taskWaitErr:
		if err != nil {
			return err
		}

		return postWaitTask(ctx, taskID, s, a.GetOut())
	case <-time.After(time.Duration(c.timeoutMins) * time.Minute):
		taskWaitCancel()
		return fmt.Errorf("timed out waiting for the task to finish")
	}
}

func waitTask(ctx context.Context, taskWaitErr chan error, taskID string, s *swarming.Service, w io.Writer) {
	// Repeatedly attempt to check whether the task is finished.
	// Returning after either a success or a maximum attempt count of errors happen or a timeout is reached.
	defer close(taskWaitErr)
	repeatedErr := 0
	sleepInterval := time.Duration(15 * time.Second)
	maxServiceDowntime := time.Duration(15 * time.Minute)
	for {
		results, err := getSwarmingResultsForIds(ctx, []string{taskID}, s)
		if err != nil {
			if ctx.Err() != nil {
				taskWaitErr <- err
				return
			}
			fmt.Fprintln(w, err)
			repeatedErr++
			if repeatedErr >= int(maxServiceDowntime/sleepInterval) {
				taskWaitErr <- err
				return
			}
			if err = sleepOrCancel(ctx, sleepInterval); err != nil {
				taskWaitErr <- err
				return
			}
			continue
		}
		repeatedErr = 0
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
		// Only retry when State=RUNNING or PENDING
		if s := results[0].State; s != "RUNNING" && s != "PENDING" {
			return
		}
		if err = sleepOrCancel(ctx, sleepInterval); err != nil {
			taskWaitErr <- err
			return
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
		childResults[i] = &taskResult{Name: c.Name, State: c.State, Failure: c.Failure}
	}
	tr := &taskResult{Name: results[0].Name, State: results[0].State, Failure: results[0].Failure}
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
