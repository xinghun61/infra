// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"io"
	"text/tabwriter"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// ListRemovedDuts subcommand: ListRemovedDuts a DUT from a drone.
var ListRemovedDuts = &subcommands.Command{
	UsageLine: "list-removed-duts [-dev]",
	ShortDesc: "list removed DUTs",
	LongDesc: `List removed DUTs.

Removed DUTs are DUTs that are not assigned to drones.  They exist in
the inventory but cannot run any tasks.  Use assign-duts to assign the
DUTs to a drone.

Removed DUTs do not belong in any environment (e.g. dev or prod).  The
-dev flag controls which crosskylabadmin server this command talks to,
which may return different results, e.g., if there is a bug in the dev
crosskylabadmin server.  Usually dev and prod should return the same
results.
`,
	CommandRun: func() subcommands.CommandRun {
		c := &listRemovedDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type listRemovedDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *listRemovedDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *listRemovedDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
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
	resp, err := ic.ListRemovedDuts(ctx, &fleet.ListRemovedDutsRequest{})
	if err != nil {
		return err
	}
	return printRemovedDUTs(a.GetOut(), resp)
}

func printRemovedDUTs(w io.Writer, resp *fleet.ListRemovedDutsResponse) error {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	fmt.Fprintf(tw, "Hostname\tModel\tBug\tComment\tExpires\t\n")
	for _, d := range resp.GetDuts() {
		var ts string
		if t, err := ptypes.Timestamp(d.GetExpireTime()); err == nil {
			ts = t.Format(time.RFC1123)
		}
		fmt.Fprintf(tw, "%s\t%s\t%s\t%s\t%s\t\n",
			d.GetHostname(),
			d.GetModel(),
			d.GetBug(),
			d.GetComment(),
			ts)
	}
	return tw.Flush()
}
