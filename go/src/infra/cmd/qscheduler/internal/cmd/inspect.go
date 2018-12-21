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

// Inspect subcommand: Inspect a qscheduler pool.
var Inspect = &subcommands.Command{
	UsageLine: "inspect",
	ShortDesc: "Inspect a qscheduler pool",
	LongDesc:  "Inspect a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &inspectRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.poolID, "id", "", "Scheduler ID to inspect.")

		return c
	},
}

type inspectRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	poolID string
}

func (c *inspectRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)

	if c.poolID == "" {
		fmt.Fprintf(os.Stderr, "Must specify id.\n")
		return 1
	}

	viewService, err := newViewClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create qsview client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.InspectPoolRequest{
		PoolId: c.poolID,
	}

	resp, err := viewService.InspectPool(ctx, req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to inspect scheduler, due to error: %s\n", err.Error())
		return 1
	}

	// TODO(akeshet): Come up with a prettier format than stringified proto.
	fmt.Println(resp)

	return 0
}
