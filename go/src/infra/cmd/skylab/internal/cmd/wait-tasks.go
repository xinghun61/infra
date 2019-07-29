// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/site"
)

// WaitTasks subcommand: wait for tasks to finish.
var WaitTasks = &subcommands.Command{
	UsageLine: "wait-tasks [FLAGS...] TASK_ID...",
	ShortDesc: "NOT YET IMPLEMENTED. wait for tasks to complete",
	LongDesc:  `NOT YET IMPLEMENTED. Wait for tasks with the given ids to complete, and summarize their results.`,
	CommandRun: func() subcommands.CommandRun {
		c := &waitTasksRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", -1, "The maxinum number of minutes to wait for the task to finish. Default: no timeout.")
		c.Flags.BoolVar(&c.buildBucket, "bb", false, "(Expert use only, not a stable API) use buildbucket recipe backend. If specified, TASK_ID is interpreted as a buildbucket task id.")
		return c
	},
}

type waitTasksRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	envFlags    envFlags
	timeoutMins int
	buildBucket bool
}

func (c *waitTasksRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *waitTasksRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var err error

	uniqueIDs := stringset.NewFromSlice(args...)
	var results <-chan waitItem

	ctx := cli.GetContext(a, c, env)

	switch c.buildBucket {
	case true:
		results = waitMultiBuildbucket(ctx, uniqueIDs)
	case false:
		results = waitMultiSwarming(ctx, uniqueIDs)
	}

	resultMap, err := consumeToMap(ctx, len(uniqueIDs), results)
	if err != nil {
		return err
	}

	output := make([]waitTaskResult, len(args))
	for i, ID := range args {
		output[i] = *resultMap[ID]
	}

	outputJSON, err := json.Marshal(output)
	if err != nil {
		return err
	}

	fmt.Fprintf(a.GetOut(), string(outputJSON))

	return nil
}

func consumeToMap(ctx context.Context, items int, results <-chan waitItem) (map[string]*waitTaskResult, error) {
	resultMap := make(map[string]*waitTaskResult)
	for {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case r, ok := <-results:
			if !ok {
				return nil, errors.New("results channel closed unexpectedly")
			}
			if r.err != nil {
				return nil, r.err
			}
			resultMap[r.ID] = r.result
			if len(resultMap) == items {
				// All results collected.
				return resultMap, nil
			}
		}
	}
}

type waitItem struct {
	result *waitTaskResult
	ID     string
	err    error
}

func waitMultiSwarming(ctx context.Context, IDs stringset.Set) <-chan waitItem {
	results := make(chan waitItem)
	go func() {
		defer close(results)
		results <- waitItem{err: errors.New("not yet implemented")}
	}()
	return results
}

func waitMultiBuildbucket(ctx context.Context, IDs stringset.Set) <-chan waitItem {
	results := make(chan waitItem)
	go func() {
		defer close(results)
		results <- waitItem{err: errors.New("not yet implemented")}
	}()
	return results
}
