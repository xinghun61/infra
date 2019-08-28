// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"infra/cmd/skylab/internal/bb"
	"infra/cmd/skylab/internal/logutils"
	"infra/cmd/skylab/internal/site"
	"io"
	"strconv"
	"time"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_tool"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

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
		c.Flags.BoolVar(&c.buildBucket, "bb", true, "(Default: True) Use buildbucket recipe backend. If so, TASK_ID is interpreted as a buildbucket task id.")
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

func (c *waitTaskRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *waitTaskRun) innerRun(a subcommands.Application, env subcommands.Env) error {
	var result *skylab_tool.WaitTaskResult
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

func (c *waitTaskRun) innerRunSwarming(a subcommands.Application, env subcommands.Env) (*skylab_tool.WaitTaskResult, error) {
	taskID := c.Flags.Arg(0)
	if taskID == "" {
		return nil, NewUsageError(c.Flags, "missing swarming task ID")
	}

	ctx := cli.GetContext(a, c, env)
	ctx, cancel := maybeWithTimeout(ctx, c.timeoutMins)
	defer cancel(context.Canceled)

	client, err := newSwarmingClient(ctx, c.authFlags, c.envFlags.Env())
	if err != nil {
		return nil, err
	}

	if err = waitSwarmingTask(ctx, taskID, client); err != nil {
		return nil, err
	}

	return extractSwarmingResult(ctx, taskID, client)
}

func (c *waitTaskRun) innerRunBuildbucket(a subcommands.Application, env subcommands.Env) (*skylab_tool.WaitTaskResult, error) {
	taskID, err := parseBBTaskID(c.Flags.Arg(0))
	if err != nil {
		return nil, NewUsageError(c.Flags, err.Error())
	}

	ctx := cli.GetContext(a, c, env)
	ctx, cancel := maybeWithTimeout(ctx, c.timeoutMins)
	defer cancel(context.Canceled)

	bClient, err := bb.NewClient(ctx, c.envFlags.Env(), c.authFlags)
	if err != nil {
		return nil, err
	}

	build, err := bClient.WaitForBuild(ctx, taskID)
	if err != nil {
		return nil, err
	}
	return responseToTaskResult(bClient, build), nil
}

func parseBBTaskID(arg string) (int64, error) {
	if arg == "" {
		return -1, errors.Reason("missing buildbucket task id").Err()
	}
	ID, err := strconv.ParseInt(arg, 10, 64)
	if err != nil {
		return -1, errors.Reason("malformed buildbucket id: %s", err).Err()
	}
	return ID, nil
}

func responseToTaskResult(bClient *bb.Client, build *bb.Build) *skylab_tool.WaitTaskResult {
	buildID := build.ID
	u := bClient.BuildURL(buildID)
	// TODO(pprabhu) Add verdict to WaitTaskResult_Task and deprecate Failure /
	// Success fields.
	// Currently, we merely leave both fields unset when no definite verdict can
	// be returned.
	tr := &skylab_tool.WaitTaskResult_Task{
		Name:          "Test Platform Invocation",
		TaskRunUrl:    u,
		TaskRunId:     fmt.Sprintf("%d", buildID),
		TaskRequestId: fmt.Sprintf("%d", buildID),
		Failure:       isBuildFailed(build),
		Success:       isBuildPassed(build),
	}
	var childResults []*skylab_tool.WaitTaskResult_Task
	for _, child := range build.Response.GetTaskResults() {
		verdict := child.GetState().GetVerdict()
		failure := verdict == test_platform.TaskState_VERDICT_FAILED
		success := verdict == test_platform.TaskState_VERDICT_PASSED
		childResult := &skylab_tool.WaitTaskResult_Task{
			Name:        child.Name,
			TaskLogsUrl: child.LogUrl,
			TaskRunUrl:  child.TaskUrl,
			// Note: TaskRunID is deprecated and excluded here.
			Failure: failure,
			Success: success,
		}
		childResults = append(childResults, childResult)
	}
	return &skylab_tool.WaitTaskResult{
		ChildResults: childResults,
		Result:       tr,
		// Note: Stdout it not set.
	}
}

func isBuildFailed(build *bb.Build) bool {
	return build.Response != nil && build.Response.GetState().GetVerdict() == test_platform.TaskState_VERDICT_FAILED
}

func isBuildPassed(build *bb.Build) bool {
	return build.Response != nil && build.Response.GetState().GetVerdict() == test_platform.TaskState_VERDICT_PASSED
}

// waitSwarmingTask waits until the task with the given ID has completed.
//
// It returns an error if the given context was cancelled or in case of swarming
// rpc failures (after transient retry).
func waitSwarmingTask(ctx context.Context, taskID string, t *swarming.Client) error {
	sleepInterval := time.Duration(15 * time.Second)
	throttledLogger := logutils.NewThrottledInfoLogger(logging.Get(ctx), 5*time.Minute)
	progressMessage := fmt.Sprintf("Still waiting for result from task ID %s", taskID)
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
		throttledLogger.MaybeLog(progressMessage)
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

func asTaskResult(s *swarming_api.SwarmingRpcsTaskResult) *skylab_tool.WaitTaskResult_Task {
	return &skylab_tool.WaitTaskResult_Task{
		Name:  s.Name,
		State: s.State,
		// TODO(crbug.com/964573): Deprecate this field.
		Failure:       s.Failure,
		Success:       !s.Failure && (s.State == "COMPLETED" || s.State == "COMPLETED_SUCCESS"),
		TaskRunId:     s.RunId,
		TaskRequestId: s.TaskId,
	}
}

func extractSwarmingResult(ctx context.Context, taskID string, t *swarming.Client) (*skylab_tool.WaitTaskResult, error) {
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
	childResults := make([]*skylab_tool.WaitTaskResult_Task, len(childs))
	for i, c := range childs {
		childResults[i] = asTaskResult(c)
	}
	tr := asTaskResult(results[0])
	result := &skylab_tool.WaitTaskResult{
		Result:       tr,
		Stdout:       stdouts[0].Output,
		ChildResults: childResults,
	}
	return result, nil
}

func printJSONResults(w io.Writer, m *skylab_tool.WaitTaskResult) {
	err := jsonPBMarshaller.Marshal(w, m)
	if err != nil {
		panic(err)
	}
}
