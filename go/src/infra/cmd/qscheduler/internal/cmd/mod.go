// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"

	"github.com/golang/protobuf/ptypes/wrappers"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

// Mod subcommand: Modify a qscheduler pool.
var Mod = &subcommands.Command{
	UsageLine: "mod [-allow-preemption ALLOW] POOL_ID",
	ShortDesc: "modify a qscheduler pool",
	LongDesc:  "Modify a qscheduler pool's global configuration.",
	CommandRun: func() subcommands.CommandRun {
		c := &modRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.Var(nullableBoolValue(&c.allowPreemption), "allow-preemption", "Allow preemption.")
		c.Flags.Var(nullableInt32Value(&c.botExpiry), "bot-expiry-seconds", "Number of seconds after which idle bots expire.")

		return c
	},
}

type modRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	allowPreemption *bool
	botExpiry       *int32
}

// validate validates command line arguments.
func (c *modRun) validate(args []string) error {
	if len(args) == 0 {
		return errors.New("missing POOL_ID")
	}

	if len(args) > 1 {
		return errors.New("too many arguments")
	}

	return nil
}

func (c *modRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validate(args); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
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

	req := &qscheduler.ModSchedulerPoolRequest{
		PoolId: poolID,
	}

	if c.allowPreemption != nil {
		req.DisablePreemption = &wrappers.BoolValue{Value: !*c.allowPreemption}
	}
	if c.botExpiry != nil {
		req.BotExpirationSeconds = &wrappers.Int32Value{Value: *c.botExpiry}
	}

	_, err = adminService.ModSchedulerPool(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to modify scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Fprintf(a.GetOut(), "qscheduler: Modified scheduler %s\n", poolID)

	return 0
}
