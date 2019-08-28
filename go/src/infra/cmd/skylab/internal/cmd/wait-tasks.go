// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"sync"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_tool"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/bb"
	"infra/cmd/skylab/internal/site"
)

// WaitTasks subcommand: wait for tasks to finish.
var WaitTasks = &subcommands.Command{
	UsageLine: "wait-tasks [FLAGS...] TASK_ID...",
	ShortDesc: "wait for tasks to complete",
	LongDesc:  `Wait for tasks with the given ids to complete, and summarize their results.`,
	CommandRun: func() subcommands.CommandRun {
		c := &waitTasksRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", -1, "The maxinum number of minutes to wait for the task to finish. Default: no timeout.")
		c.Flags.BoolVar(&c.buildBucket, "bb", true, "(Default: True) Use buildbucket recipe backend. If so, TASK_ID is interpreted as a buildbucket task id.")
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
	uniqueIDs := stringset.NewFromSlice(args...)

	ctx := cli.GetContext(a, c, env)
	ctx, cancel := maybeWithTimeout(ctx, c.timeoutMins)
	defer cancel(context.Canceled)

	var results <-chan waitItem
	var err error
	switch c.buildBucket {
	case true:
		results, err = waitMultiBuildbucket(ctx, uniqueIDs, c.authFlags, c.envFlags.Env())
	case false:
		results, err = waitMultiSwarming(ctx, uniqueIDs, c.authFlags, c.envFlags.Env())
	}
	if err != nil {
		return err
	}

	// Ensure results channel is eventually fully consumed.
	defer func() {
		go func() {
			for range results {
			}
		}()
	}()

	// Consume results. If an error occurs, save it for later logging, but
	// still use the partial results.
	resultMap, consumeErr := consumeToMap(ctx, len(uniqueIDs), results)

	output := &skylab_tool.WaitTasksResult{Incomplete: consumeErr != nil}
	for _, ID := range args {
		r, ok := resultMap[ID]
		if !ok {
			// Results for the given ID never appeared; instead use a "missing"
			// placeholder.
			// TODO(akeshet): Come up with a clearer representation of missing
			// results.
			r = &skylab_tool.WaitTaskResult{
				Result: &skylab_tool.WaitTaskResult_Task{
					TaskRequestId: ID,
				},
			}
		}
		output.Results = append(output.Results, r)
	}

	outputJSON, err := jsonPBMarshaller.MarshalToString(output)
	if err != nil {
		return err
	}

	fmt.Fprintf(a.GetOut(), string(outputJSON))

	return consumeErr
}

// consumeToMap consumes per-task results from results channel, into an ID-to-results
// map. It returns when either |items| unique IDs are collected, context expires,
// or an error occurs.
//
// If an error occurs, it returns the partial results that were collected
// prior to the error.
func consumeToMap(ctx context.Context, items int, results <-chan waitItem) (map[string]*skylab_tool.WaitTaskResult, error) {
	resultMap := make(map[string]*skylab_tool.WaitTaskResult)
	for {
		if len(resultMap) == items {
			return resultMap, nil
		}

		select {
		case <-ctx.Done():
			return resultMap, ctx.Err()
		case r, ok := <-results:
			if !ok {
				// Context and result channel close nearly simultaneously in case
				// of wait-tasks timeout. In such a case, it is preferable to
				// return the context's error message, which is more informative.
				err := ctx.Err()
				if err == nil {
					errors.New("results channel closed unexpectedly")
				}
				return resultMap, err
			}
			if r.err != nil {
				return resultMap, r.err
			}
			resultMap[r.ID] = r.result
		}
	}
}

type waitItem struct {
	result *skylab_tool.WaitTaskResult
	ID     string
	err    error
}

func waitMultiSwarming(ctx context.Context, IDs stringset.Set, authFlags authcli.Flags, env site.Environment) (<-chan waitItem, error) {
	client, err := newSwarmingClient(ctx, authFlags, env)
	if err != nil {
		return nil, err
	}

	results := make(chan waitItem)
	go func() {
		defer close(results)

		// Wait for each task in separate goroutine.
		wg := sync.WaitGroup{}
		wg.Add(IDs.Len())
		for _, ID := range IDs.ToSlice() {
			go func(ID string) {
				defer wg.Done()

				err := waitSwarmingTask(ctx, ID, client)
				if err != nil {
					select {
					case results <- waitItem{err: err}:
					case <-ctx.Done():
					}
					return
				}

				result, err := extractSwarmingResult(ctx, ID, client)
				item := waitItem{result: result, err: err, ID: ID}
				select {
				case results <- item:
				case <-ctx.Done():
				}
				return
			}(ID)
		}
		// Wait for all child routines terminate.
		wg.Wait()
	}()

	return results, nil
}

func waitMultiBuildbucket(ctx context.Context, IDs stringset.Set, authFlags authcli.Flags, env site.Environment) (<-chan waitItem, error) {
	parsedIDs, err := parseBBTaskIDs(IDs.ToSlice())
	if err != nil {
		return nil, err
	}

	client, err := bb.NewClient(ctx, env, authFlags)
	if err != nil {
		return nil, err
	}

	results := make(chan waitItem)
	go func() {
		defer close(results)

		// Wait for each task in separate goroutine.
		wg := sync.WaitGroup{}
		wg.Add(len(parsedIDs))

		for ID, parsedID := range parsedIDs {
			go func(ID string, parsedID int64) {
				build, err := client.WaitForBuild(ctx, parsedID)
				var result *skylab_tool.WaitTaskResult
				if build != nil {
					result = responseToTaskResult(client, build)
				}
				item := waitItem{result: result, err: err, ID: ID}
				select {
				case results <- item:
				case <-ctx.Done():
				}

				wg.Done()
			}(ID, parsedID)
		}
		// Wait for all child routines terminate.
		wg.Wait()
	}()

	return results, nil
}

func parseBBTaskIDs(args []string) (map[string]int64, error) {
	IDs := make(map[string]int64)
	for _, a := range args {
		ID, err := parseBBTaskID(a)
		if err != nil {
			return nil, err
		}
		IDs[a] = ID
	}
	return IDs, nil
}
