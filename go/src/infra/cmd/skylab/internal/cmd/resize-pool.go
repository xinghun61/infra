// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strconv"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// ResizePool subcommand: Resize DUT pools
var ResizePool = &subcommands.Command{
	UsageLine: "resize-pool [-spare SPARE] TARGET MODEL SIZE",
	ShortDesc: "change DUT pool allocations",
	LongDesc: `
Change the number of DUTs in the TARGET pool for MODEL to SIZE.

Any DUTs that need to be added or removed from the TARGET pool will be
taken from or returned to the SPARE pool.`,
	CommandRun: func() subcommands.CommandRun {
		c := &resizePoolRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)

		c.Flags.StringVar(&c.spare, "spare", "DUT_POOL_SUITES", "Spare pool to use.")
		return c
	},
}

type resizePoolRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	spare string
}

func (c *resizePoolRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *resizePoolRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(args) != 3 {
		return NewUsageError(c.Flags, "want 3 arguments, have %d", len(args))
	}
	target := args[0]
	model := args[1]
	s, err := strconv.ParseInt(args[2], 0, 32)
	if err != nil {
		return NewUsageError(c.Flags, "want positive 32 bit integer for size, have %s", args[1])
	}
	size := int32(s)

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

	return c.resizePool(ctx, ic, model, target, size)
}

func (c *resizePoolRun) resizePool(ctx context.Context, ic fleet.InventoryClient, model string, target string, size int32) error {
	resp, err := ic.ResizePool(
		ctx,
		&fleet.ResizePoolRequest{
			DutSelector: &fleet.DutSelector{
				Model: model,
			},
			TargetPool:     target,
			TargetPoolSize: size,
			SparePool:      c.spare,
		},
	)
	if err != nil {
		return errors.Annotate(err, "resize pool").Err()
	}

	c.printResult(resp)
	return nil
}

func (c *resizePoolRun) printResult(resp *fleet.ResizePoolResponse) {
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "Resize pool succeeded\n")
	fmt.Fprintf(w, "Inventory changes committed at:\t%s\n", resp.GetUrl())
	if len(resp.GetChanges()) > 0 {
		fmt.Fprintf(w, "Inventory changes:\n")
		for _, c := range resp.Changes {
			fmt.Fprintf(w, "\t%s: %s\t->\t%s\n", c.DutId, c.OldPool, c.NewPool)
		}
	}
}
