// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"
)

// RemoveDuts subcommand: RemoveDuts a DUT from a drone.
var RemoveDuts = &subcommands.Command{
	UsageLine: "remove-duts -bug BUG [-delete] [FLAGS] DUT...",
	ShortDesc: "remove DUTs from a drone",
	LongDesc: `Remove DUTs from a drone

-bug is required unless -delete is passed.

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
		c.Flags.BoolVar(&c.delete, "delete", false, "Delete DUT from inventory.")
		c.removalReason.Register(&c.Flags)
		return c
	},
}

type removeDutsRun struct {
	subcommands.CommandRunBase
	authFlags     authcli.Flags
	envFlags      envFlags
	server        string
	delete        bool
	removalReason removalReason
}

func (c *removeDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *removeDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
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
	modified, err := c.removeDUTs(ctx, ic, a.GetOut())
	if err != nil {
		return err
	}
	if c.delete {
		mod, err := c.deleteDUTs(ctx, ic, a.GetOut())
		if err != nil {
			return err
		}
		modified = modified || mod
	}
	if !modified {
		fmt.Fprintln(a.GetOut(), "No DUTs modified")
		return nil
	}
	return nil
}

func (c *removeDutsRun) validateArgs() error {
	var errs []string
	if c.Flags.NArg() == 0 {
		errs = append(errs, "must specify at least 1 DUT")
	}
	if c.removalReason.bug == "" && !c.delete {
		errs = append(errs, "-bug is required when not deleting")
	}
	if !validBug(c.removalReason.bug) {
		errs = append(errs, "-bug must match crbug.com/NNNN or b/NNNN")
	}
	// Limit to roughly one line, like a commit message first line.
	if len(c.removalReason.comment) > 80 {
		errs = append(errs, "-reason is too long (use the bug for details)")
	}
	if len(errs) > 0 {
		return NewUsageError(c.Flags, strings.Join(errs, ", "))
	}
	return nil
}

// validBug returns true if the given bug string is acceptably formatted.
func validBug(bug string) bool {
	if strings.HasPrefix(bug, "b/") {
		return true
	}
	if strings.HasPrefix(bug, "crbug.com/") {
		return true
	}
	return false
}

func (c *removeDutsRun) removeDUTs(ctx context.Context, ic fleet.InventoryClient, stdout io.Writer) (modified bool, err error) {
	req, err := removeRequest(c.server, c.Flags.Args(), c.removalReason)
	if err != nil {
		return false, err
	}
	resp, err := ic.RemoveDutsFromDrones(ctx, &req)
	if err != nil {
		return false, err
	}
	if resp.Url == "" {
		return false, nil
	}
	_ = printRemovals(stdout, resp)
	return true, nil
}

// removeRequest builds a RPC remove request.
func removeRequest(server string, hostnames []string, rr removalReason) (fleet.RemoveDutsFromDronesRequest, error) {
	req := fleet.RemoveDutsFromDronesRequest{
		Removals: make([]*fleet.RemoveDutsFromDronesRequest_Item, len(hostnames)),
	}
	reason := inventory.RemovalReason{
		Bug:        &rr.bug,
		Comment:    &rr.comment,
		ExpireTime: protoTimestamp(rr.expire),
	}
	enc, err := proto.Marshal(&reason)
	if err != nil {
		return req, errors.Annotate(err, "make remove request").Err()
	}
	for i, hn := range hostnames {
		req.Removals[i] = &fleet.RemoveDutsFromDronesRequest_Item{
			DutHostname:   hn,
			DroneHostname: server,
			RemovalReason: enc,
		}
	}
	return req, nil
}

func protoTimestamp(t time.Time) *inventory.Timestamp {
	s := t.Unix()
	ns := int32(t.Nanosecond())
	return &inventory.Timestamp{
		Seconds: &s,
		Nanos:   &ns,
	}
}

func (c *removeDutsRun) deleteDUTs(ctx context.Context, ic fleet.InventoryClient, stdout io.Writer) (modified bool, err error) {
	resp, err := ic.DeleteDuts(ctx, &fleet.DeleteDutsRequest{Hostnames: c.Flags.Args()})
	if err != nil {
		return false, err
	}
	if resp.ChangeUrl == "" {
		return false, nil
	}
	_ = printDeletions(stdout, resp)
	return true, nil
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
