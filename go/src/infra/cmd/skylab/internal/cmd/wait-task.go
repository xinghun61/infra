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
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/swarming"
)

// WaitTask subcommand: wait for a task to finish.
var WaitTask = &subcommands.Command{
	UsageLine: "wait-task [FLAGS...] TASK_ID",
	ShortDesc: "wait for a task to complete",
	LongDesc:  `Wait for the task with the given swarming task id to complete, and summarize its results.`,
	CommandRun: func() subcommands.CommandRun {
		c := &waitTaskRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", -1, "The maxinum number of minutes to wait for the task to finish. Default: no timeout.")
		c.Flags.BoolVar(&c.buildBucket, "bb", false, "(Expert use only, not a stable API) use buildbucket recipe backend. If specified, TASK_ID is interpreted as a buildbucket task id.")
		return c
	},
}

type waitTaskRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	envFlags    envFlags
	timeoutMins int
	buildBucket bool
}

// TODO(crbug.com/988611): Use a proto defined format for the wait-task output.
type taskResult struct {
	Name  string `json:"name"`
	State string `json:"state"`
	// TODO(crbug.com/964573): Deprecate this field.
	Failure bool `json:"failure"`
	Success bool `json:"success"`

	// Note: These fields are a little problematic, because they are not independently
	// meaningful to the caller; their meaning depends on the namespace (buildbucket vs. swarming)
	// and, in the case of swarming, environment (dev vs. prod).
	// Still, they are used by some clients, so preserved for now.
	// Note the distinction between TaskRunID and TaskRequestID: in buildbucket runs,
	// these will be equal. In swarming runs, they will differ in the last character
	// (this is the difference between a swarming run id and request id).
	TaskRunID     string `json:"task-run-id"`
	TaskRequestID string `json:"task-request-id"`

	// Note: these URL fields are only populated for -bb runs; eventually,
	// non-bb runs will be deprecated.
	TaskRunURL  string `json:"task-run-url"`
	TaskLogsURL string `json:"task-logs-url"`
}

// TODO(crbug.com/988611): Use a proto defined format for the wait-task output.
type waitTaskResult struct {
	TaskResult   *taskResult   `json:"task-result"`
	Stdout       string        `json:"stdout"`
	ChildResults []*taskResult `json:"child-results"`
}

func (c *waitTaskRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *waitTaskRun) innerRun(a subcommands.Application, env subcommands.Env) error {
	var result *waitTaskResult
	var err error
	switch c.buildBucket {
	case true:
		result, err = c.innerRunBuildbucket(a, env)
	case false:
		result, err = c.innerRunSwarming(a, env)
	}

	if err != nil {
		return err
	}

	printJSONResults(a.GetOut(), result)
	return nil
}

func (c *waitTaskRun) innerRunSwarming(a subcommands.Application, env subcommands.Env) (*waitTaskResult, error) {
	taskID := c.Flags.Arg(0)
	if taskID == "" {
		return nil, NewUsageError(c.Flags, "missing swarming task ID")
	}

	ctx := cli.GetContext(a, c, env)
	ctx, cancel := withTimeout(ctx, c.timeoutMins)
	defer cancel()

	client, err := swarmingClient(ctx, c.authFlags, c.envFlags.Env())

	if err = waitSwarmingTask(ctx, taskID, client); err != nil {
		if err == context.DeadlineExceeded {
			return nil, errors.New("timed out waiting for task to complete")
		}
		return nil, err
	}

	return extractSwarmingResult(ctx, taskID, client)
}

// TODO(akeshet): Move to common file.
func swarmingClient(ctx context.Context, authFlags authcli.Flags, env site.Environment) (*swarming.Client, error) {
	h, err := httpClient(ctx, &authFlags)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create http client").Err()
	}
	client, err := swarming.New(ctx, h, env.SwarmingService)
	if err != nil {
		return nil, err
	}
	return client, nil
}

func (c *waitTaskRun) innerRunBuildbucket(a subcommands.Application, env subcommands.Env) (*waitTaskResult, error) {
	taskIDString := c.Flags.Arg(0)
	if taskIDString == "" {
		return nil, NewUsageError(c.Flags, "missing buildbucket task id")
	}

	ctx := cli.GetContext(a, c, env)
	ctx, cancel := withTimeout(ctx, c.timeoutMins)
	defer cancel()

	bClient, err := bbClient(ctx, c.envFlags.Env(), c.authFlags)
	if err != nil {
		return nil, err
	}

	return waitBuildbucketTask(ctx, taskIDString, bClient, c.envFlags.Env())
}

func responseToTaskResult(e site.Environment, buildID int64, response *steps.ExecuteResponse) *waitTaskResult {
	u := bbURL(e, buildID)
	verdict := response.GetState().GetVerdict()
	failure := verdict == test_platform.TaskState_VERDICT_FAILED
	success := verdict == test_platform.TaskState_VERDICT_PASSED
	tr := &taskResult{
		Name:          "Test Platform Invocation",
		TaskRunURL:    u,
		TaskRunID:     fmt.Sprintf("%d", buildID),
		TaskRequestID: fmt.Sprintf("%d", buildID),
		Failure:       failure,
		Success:       success,
	}
	var childResults []*taskResult
	for _, child := range response.TaskResults {
		verdict := child.GetState().GetVerdict()
		failure := verdict == test_platform.TaskState_VERDICT_FAILED
		success := verdict == test_platform.TaskState_VERDICT_PASSED
		childResult := &taskResult{
			Name:        child.Name,
			TaskLogsURL: child.LogUrl,
			TaskRunURL:  child.TaskUrl,
			// Note: TaskRunID is deprecated and excluded here.
			Failure: failure,
			Success: success,
		}
		childResults = append(childResults, childResult)
	}
	return &waitTaskResult{
		ChildResults: childResults,
		TaskResult:   tr,
		// Note: Stdout it not set.
	}
}

// waitSwarmingTask waits until the task with the given ID has completed.
//
// It returns an error if the given context was cancelled or in case of swarming
// rpc failures (after transient retry).
func waitSwarmingTask(ctx context.Context, taskID string, t *swarming.Client) error {
	sleepInterval := time.Duration(15 * time.Second)
	for {
		results, err := t.GetResults(ctx, []string{taskID})
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

func asTaskResult(s *swarming_api.SwarmingRpcsTaskResult) *taskResult {
	return &taskResult{
		Name:  s.Name,
		State: s.State,
		// TODO(crbug.com/964573): Deprecate this field.
		Failure:       s.Failure,
		Success:       !s.Failure && (s.State == "COMPLETED" || s.State == "COMPLETED_SUCCESS"),
		TaskRunID:     s.RunId,
		TaskRequestID: s.TaskId,
	}
}

func extractSwarmingResult(ctx context.Context, taskID string, t *swarming.Client) (*waitTaskResult, error) {
	results, err := t.GetResults(ctx, []string{taskID})
	if err != nil {
		return nil, err
	}
	stdouts, err := t.GetTaskOutputs(ctx, []string{taskID})
	if err != nil {
		return nil, err
	}
	childs, err := t.GetResults(ctx, results[0].ChildrenTaskIds)
	if err != nil {
		return nil, err
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
	return result, nil
}

func printJSONResults(w io.Writer, m *waitTaskResult) {
	outputJSON, err := json.Marshal(m)
	if err != nil {
		panic(err)
	}
	fmt.Fprintf(w, string(outputJSON))
}
