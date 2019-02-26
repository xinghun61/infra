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
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/flag"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
	"infra/qscheduler/qslib/protos"
)

// Create subcommand: Create a qscheduler pool.
var Create = &subcommands.Command{
	UsageLine: "create [-label KEY:VALUE...] POOL_ID",
	ShortDesc: "Create a qscheduler pool",
	LongDesc:  "Create a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &createRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.Var(flag.StringSlice(&c.labels), "label",
			"Label that will be used by all tasks and bots for this scheduler, specified in "+
				"the form foo:bar. May be specified multiple times.")

		return c
	},
}

type createRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	labels []string
}

func (c *createRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "missing POOL_ID\n")
		c.Flags.Usage()
		return 1
	}

	if len(args) > 1 {
		fmt.Fprintf(os.Stderr, "too many arguments\n")
		c.Flags.Usage()
		return 1
	}

	poolID := args[0]

	for _, l := range c.labels {
		_, v := strpair.Parse(l)
		if v == "" {
			fmt.Fprintf(os.Stderr, "Incorrectly formatted label %s.\n", l)
			return 1
		}
	}

	ctx := cli.GetContext(a, c, env)

	adminService, err := newAdminClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create qsadmin client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.CreateSchedulerPoolRequest{
		PoolId: poolID,
		Config: &protos.SchedulerConfig{Labels: c.labels},
	}

	_, err = adminService.CreateSchedulerPool(ctx, req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Printf("Created scheduler %s\n", poolID)

	return 0
}
