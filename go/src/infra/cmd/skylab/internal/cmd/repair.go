// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/site"
)

// Repair subcommand: Repair hosts.
var Repair = &subcommands.Command{
	UsageLine: "repair [HOST...]",
	ShortDesc: "Repair hosts",
	LongDesc:  "Repair hosts.",
	CommandRun: func() subcommands.CommandRun {
		c := &repairRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type repairRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *repairRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *repairRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	e := c.envFlags.Env()
	s, err := newSwarmingService(ctx, c.authFlags, e)
	if err != nil {
		return errors.Annotate(err, "failed to create Swarming client").Err()
	}

	for _, host := range args {
		id, err := createRepairTask(ctx, s, e, host)
		if err != nil {
			return err
		}
		fmt.Fprintf(a.GetOut(), "Created Swarming task %s for host %s\n", swarmingTaskURL(e, id), host)
	}
	return nil
}

func createRepairTask(ctx context.Context, s *swarming.Service, e site.Environment, host string) (taskID string, err error) {
	log := generateAnnotationURL(e)
	slices := []*swarming.SwarmingRpcsTaskSlice{{
		ExpirationSecs: 600,
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command: []string{
				"/opt/infra-tools/skylab_swarming_worker",
				"-task-name", "admin_repair",
				"-logdog-annotation-url", log,
			},
			Dimensions: []*swarming.SwarmingRpcsStringPair{
				{Key: "pool", Value: "ChromeOSSkylab"},
				{Key: "dut_name", Value: host},
			},
			ExecutionTimeoutSecs: 5400,
		},
		WaitForCapacity: true,
	}}
	r := newTaskRequest(
		"admin_repair",
		[]string{
			fmt.Sprintf("log_location:%s", log),
			fmt.Sprintf("luci_project:%s", e.LUCIProject),
			"pool:ChromeOSSkylab",
			"skylab:manual_trigger",
		},
		slices,
		25)
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	resp, err := s.Tasks.New(r).Context(ctx).Do()
	if err != nil {
		return "", errors.Annotate(err, "failed to create task").Err()
	}
	return resp.TaskId, nil
}
