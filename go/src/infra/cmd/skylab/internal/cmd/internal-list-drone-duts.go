// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"fmt"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// InternalListDroneDuts subcommand: List DUTs for a drone.
var InternalListDroneDuts = &subcommands.Command{
	UsageLine: "internal-list-drone-duts HOSTNAME",
	ShortDesc: "list DUTs for a drone",
	LongDesc: `List DUTs for a drone.

For internal use only.`,
	CommandRun: func() subcommands.CommandRun {
		c := &internalListDroneDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type internalListDroneDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *internalListDroneDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *internalListDroneDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(args) != 1 {
		return NewUsageError(c.Flags, "exactly one HOSTNAME must be provided")
	}
	hostname := args[0]
	ctx := cli.GetContext(a, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	siteEnv := c.envFlags.Env()
	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    siteEnv.AdminService,
		Options: site.DefaultPRPCOptions,
	})
	req := fleet.GetDroneConfigRequest{Hostname: hostname}
	res, err := ic.GetDroneConfig(ctx, &req)
	if err != nil {
		return err
	}

	bw := bufio.NewWriter(a.GetOut())
	defer bw.Flush()
	for _, d := range res.GetDuts() {
		fmt.Fprintf(bw, "%s %s\n", d.GetId(), d.GetHostname())
	}
	return nil
}
