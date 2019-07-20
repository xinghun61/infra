// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"fmt"
	"text/tabwriter"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	"infra/appengine/drone-queen/api"
	"infra/cmd/skylab/internal/site"
)

// QueenInspectDuts subcommand: Inspect drone queen DUT info.
var QueenInspectDuts = &subcommands.Command{
	UsageLine: "queen-inspect-duts",
	ShortDesc: "inspect drone queen DUT info",
	LongDesc: `Inspect drone queen DUT info.

This command is for developer inspection and debugging of drone queen state.
Do not use this command as part of scripts or pipelines.
This command is unstable.

You must be in the respective inspectors group to use this.`,
	CommandRun: func() subcommands.CommandRun {
		c := &queenInspectDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type queenInspectDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *queenInspectDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), errors.Annotate(err, "queen-inspect-duts").Err())
		return 1
	}
	return 0
}

func (c *queenInspectDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()
	ic := api.NewInspectPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.QueenService,
		Options: site.DefaultPRPCOptions,
	})

	res, err := ic.ListDuts(ctx, &api.ListDutsRequest{})
	if err != nil {
		return err
	}

	bw := bufio.NewWriter(a.GetOut())
	defer bw.Flush()
	tw := tabwriter.NewWriter(bw, 0, 2, 2, ' ', 0)
	defer tw.Flush()
	fmt.Fprintf(tw, "DUT\tDrone\tDraining\t\n")
	for _, d := range res.GetDuts() {
		fmt.Fprintf(tw, "%v\t%v\t%v\t\n",
			d.GetId(), d.GetAssignedDrone(), d.GetDraining())
	}
	return nil
}
