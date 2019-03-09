// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

// Inspect subcommand: Inspect a qscheduler pool.
var Inspect = &subcommands.Command{
	UsageLine: "inspect POOL_ID",
	ShortDesc: "Inspect a qscheduler pool",
	LongDesc:  "Inspect a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &inspectRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type inspectRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *inspectRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)

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

	viewService, err := newViewClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to create qsview client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.InspectPoolRequest{
		PoolId: poolID,
	}

	resp, err := viewService.InspectPool(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to inspect scheduler, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Println(proto.MarshalTextString(resp))

	return 0
}
