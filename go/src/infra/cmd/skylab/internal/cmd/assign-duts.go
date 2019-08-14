// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"
	"text/tabwriter"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// AssignDuts subcommand: AssignDuts a DUT to a drone.
var AssignDuts = &subcommands.Command{
	UsageLine: "assign-duts [-drone DRONE] [DUT...]",
	ShortDesc: "assign DUTs to a drone",
	LongDesc: `Assign DUTs to a drone.

Assigning a DUT to a drone allows the DUT to run tasks.`,
	CommandRun: func() subcommands.CommandRun {
		c := &assignDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.server, "drone", "",
			`Hostname of drone to assign DUTs to.
If omitted, one is automatically chosen.`)
		return c
	},
}

type assignDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	server    string
}

func (c *assignDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *assignDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.Flags.NArg() == 0 {
		return errors.New("must specify at least 1 DUT")
	}

	req := &fleet.AssignDutsToDronesRequest{
		Assignments: make([]*fleet.AssignDutsToDronesRequest_Item, c.Flags.NArg()),
	}

	for i, dut := range c.Flags.Args() {
		req.Assignments[i] = &fleet.AssignDutsToDronesRequest_Item{DutHostname: dut}
	}
	if c.server != "" {
		for _, a := range req.Assignments {
			a.DroneHostname = c.server
		}
	}

	ctx := cli.GetContext(a, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()
	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})

	resp, err := ic.AssignDutsToDrones(ctx, req)
	if err != nil {
		return err
	}

	if len(resp.Assigned) == 0 {
		fmt.Fprintln(a.GetErr(), "No DUTs assigned")
		return nil
	}

	t := tabwriter.NewWriter(a.GetOut(), 0, 0, 2, ' ', 0)
	fmt.Fprintln(t, resp.Url)
	fmt.Fprintln(t, "DUT ID\tAssigned to drone\t")
	for _, r := range resp.Assigned {
		fmt.Fprintf(t, "%s\t%s\t\n", r.DutId, r.DroneHostname)
	}
	t.Flush()

	return nil
}
