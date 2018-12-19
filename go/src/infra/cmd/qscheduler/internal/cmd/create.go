// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

// Create subcommand: Create a qscheduler pool.
var Create = &subcommands.Command{
	UsageLine: "create",
	ShortDesc: "Create a qscheduler pool",
	LongDesc:  "Create a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &createRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.poolID, "id", "", "usage")
		return c
	},
}

type createRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	poolID string
}

func (c *createRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)

	adminService, err := newAdminClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create qsadmin client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.CreateSchedulerPoolRequest{
		PoolId: c.poolID,
		// TODO(akeshet): Add a labels command line argument, parse it, and use it to construct
		// this config.
		Config: &qscheduler.SchedulerPoolConfig{},
	}

	_, err = adminService.CreateSchedulerPool(ctx, req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Printf("Created scheduler %s\n", c.poolID)

	return 0
}
