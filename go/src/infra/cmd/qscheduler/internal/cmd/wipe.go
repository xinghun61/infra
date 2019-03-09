// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

// Wipe subcommand: Wipe a qscheduler pool.
var Wipe = &subcommands.Command{
	UsageLine: "wipe -X POOL_ID",
	ShortDesc: "Wipe a qscheduler pool",
	LongDesc:  "Wipe a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &wipeRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.confirmed, "X", false, "I know what I'm doing, and I want to wipe out scheduler state.")
		return c
	},
}

type wipeRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	confirmed bool
}

func (c *wipeRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if !c.confirmed {
		fmt.Fprintf(a.GetErr(), "didn't specify confimation flag\n")
		c.Flags.Usage()
		return 1
	}
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

	req := &qscheduler.WipeRequest{
		PoolId: poolID,
	}

	_, err = adminService.Wipe(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to wipe scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Fprintf(a.GetOut(), "qscheduler: Wiped scheduler %s\n", poolID)

	return 0
}
