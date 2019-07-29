// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

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
	ShortDesc: "wait for tasks to complete",
	LongDesc:  `Wait for tasks with the given ids to complete, and summarize their results.`,
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
	uniqueIDs := stringset.NewFromSlice(args...)

	ctx := cli.GetContext(a, c, env)
	var cancel context.CancelFunc
	switch c.timeoutMins >= 0 {
	case true:
		ctx, cancel = context.WithTimeout(ctx, time.Duration(c.timeoutMins)*time.Minute)
	case false:
		ctx, cancel = context.WithCancel(ctx)
	}
	defer cancel()

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

	resultMap, err := consumeToMap(ctx, len(uniqueIDs), results)
	if err != nil {
		return err
	}

	output := make([]*waitTaskResult, len(args))
	for i, ID := range args {
		output[i] = resultMap[ID]
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
		if len(resultMap) == items {
			return resultMap, nil
		}

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
		}
	}
}

type waitItem struct {
	result *waitTaskResult
	ID     string
	err    error
}

func waitMultiSwarming(ctx context.Context, IDs stringset.Set, authFlags authcli.Flags, env site.Environment) (<-chan waitItem, error) {
	client, err := swarmingClient(ctx, authFlags, env)
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
	client, err := bbClient(ctx, env, authFlags)
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
				result, err := waitBuildbucketTask(ctx, ID, client, env)
				item := waitItem{result: result, err: err, ID: ID}
				select {
				case results <- item:
				case <-ctx.Done():
				}

				wg.Done()
			}(ID)
		}
		// Wait for all child routines terminate.
		wg.Wait()
	}()

	return results, nil
}
