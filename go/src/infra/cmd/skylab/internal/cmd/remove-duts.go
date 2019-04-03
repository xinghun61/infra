// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"text/tabwriter"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// RemoveDuts subcommand: RemoveDuts a DUT from a drone.
var RemoveDuts = &subcommands.Command{
	UsageLine: "remove-duts [-drone DRONE] [-delete] [DUT...]",
	ShortDesc: "remove DUTs from a drone",
	LongDesc: `Remove DUTs from a drone

-reason is required. (reason is currently unused: crbug/934067).

If -drone is given, check that the DUTs are currently assigned to that
drone.  Otherwise, the DUTs are removed from whichever drone they are
currently assigned to.

Removing DUTs from a drone stops the DUTs from being able to run
tasks.  The DUT can be assigned with assign-duts to run tasks again.

Setting -delete deletes the DUTs from the inventory entirely.  After
deleting a DUT, it would have to be deployed from scratch to run tasks
again.`,
	CommandRun: func() subcommands.CommandRun {
		c := &removeDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.server, "drone", "", "Drone to remove DUTs from.")
		c.Flags.StringVar(&c.reason, "reason", "", `Reason the DUT is being removed from drone.
Please include a bug reference, especially if the DUT should be added
back in the future.`)
		c.Flags.BoolVar(&c.delete, "delete", false, "Delete DUT from inventory.")
		return c
	},
}

type removeDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	server    string
	delete    bool
	reason    string
}

func (c *removeDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *removeDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.Flags.NArg() == 0 {
		return errors.New("must specify at least 1 DUT")
	}
	if c.reason == "" {
		return errors.New("-reason is required")
	}

	ctx := cli.GetContext(a, c, env)
	hc, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()
	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})

	req := removeRequest(c.server, c.Flags.Args())
	removalResp, err := ic.RemoveDutsFromDrones(ctx, &req)
	if err != nil {
		return err
	}
	if removalResp.Url != "" {
		_ = printRemovals(a.GetOut(), removalResp)
	}

	deletionResp := &fleet.DeleteDutsResponse{}
	if c.delete {
		deletionResp, err = ic.DeleteDuts(ctx, &fleet.DeleteDutsRequest{Hostnames: c.Flags.Args()})
		if err != nil {
			return err
		}
	}
	if deletionResp.ChangeUrl != "" {
		_ = printDeletions(a.GetOut(), deletionResp)
	}

	if removalResp.Url == "" && deletionResp.ChangeUrl == "" {
		fmt.Fprintln(a.GetOut(), "No DUTs modified")
		return nil
	}

	return nil
}

// removeRequest builds a RPC remove request.
func removeRequest(server string, hostnames []string) fleet.RemoveDutsFromDronesRequest {
	req := fleet.RemoveDutsFromDronesRequest{
		Removals: make([]*fleet.RemoveDutsFromDronesRequest_Item, len(hostnames)),
	}
	for i, hn := range hostnames {
		req.Removals[i] = &fleet.RemoveDutsFromDronesRequest_Item{DutHostname: hn, DroneHostname: server}
	}
	return req
}

// printRemovals prints a table of DUT removals from drones.
func printRemovals(w io.Writer, resp *fleet.RemoveDutsFromDronesResponse) error {
	fmt.Fprintf(w, "DUT removal from drone: %s\n", resp.Url)

	t := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	fmt.Fprintln(t, "DUT ID\tRemoved from drone")
	for _, r := range resp.Removed {
		fmt.Fprintf(t, "%s\t%s\n", r.GetDutId(), r.GetDroneHostname())
	}
	return t.Flush()
}

// printDeletions prints a list of deleted DUTs.
func printDeletions(w io.Writer, resp *fleet.DeleteDutsResponse) error {
	b := bufio.NewWriter(w)
	fmt.Fprintf(b, "DUT deletion: %s\n", resp.ChangeUrl)
	fmt.Fprintln(b, "Deleted DUT IDs")
	for _, id := range resp.Ids {
		fmt.Fprintln(b, id)
	}
	return b.Flush()
}
