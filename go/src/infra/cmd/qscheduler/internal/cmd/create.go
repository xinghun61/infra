// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
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
		c.Flags.BoolVar(&c.allowPreemption, "allow-preemption", true, "Allow preemption.")
		c.Flags.Var(nullableInt32Value(&c.botExpiry), "bot-expiry-seconds", "Number of seconds after which idle bots expire.")

		return c
	},
}

type createRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	allowPreemption bool
	botExpiry       *int32
}

func (c *createRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) == 0 {
		fmt.Fprintf(a.GetErr(), "missing POOL_ID\n")
		c.Flags.Usage()
		return 1
	}

	if len(args) > 1 {
		fmt.Fprintf(a.GetErr(), "too many arguments\n")
		c.Flags.Usage()
		return 1
	}

	poolID := args[0]

	ctx := cli.GetContext(a, c, env)

	adminService, err := newAdminClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to create qsadmin client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.CreateSchedulerPoolRequest{
		PoolId: poolID,
	}
	if c.botExpiry != nil {
		req.Config.BotExpiration = ptypes.DurationProto(time.Duration(*c.botExpiry) * time.Second)
	}

	_, err = adminService.CreateSchedulerPool(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to create scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Fprintf(a.GetOut(), "qscheduler: Created scheduler %s\n", poolID)

	return 0
}
