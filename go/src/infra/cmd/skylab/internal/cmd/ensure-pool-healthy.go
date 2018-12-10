// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
	"os"
	"strings"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"
)

// EnsurePoolHealthy subcommand: Balance DUT pools
var EnsurePoolHealthy = &subcommands.Command{
	UsageLine: "ensure-pool-healthy [-dryrun] [-s spare] target model [model...]",
	ShortDesc: "Ensure DUT pool is healthy",
	LongDesc: `
Ensure that given models' target pool contains healthy DUTs.
If needed, swap in healthy DUTs from spare pool.`,
	CommandRun: func() subcommands.CommandRun {
		c := &ensurePoolHealthyRun{}
		c.authFlags.RegisterScopesFlag = true
		c.authFlags.Register(&c.Flags, WithGerritScope(site.DefaultAuthOptions))
		c.envFlags.Register(&c.Flags)

		c.Flags.BoolVar(&c.dryrun, "dryrun", false, "Dryrun mode -- do not commit inventory changes")
		c.Flags.StringVar(&c.spare, "spare", "DUT_POOL_SUITES", "DUT pool to swap in healthy DUTs from")
		return c
	},
}

type ensurePoolHealthyRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	dryrun bool
	spare  string
}

type posArgs struct {
	Models []string
	Target string
}

func (c *ensurePoolHealthyRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	pa, err := c.parseArgs(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s\n\n", err)
		c.Flags.Usage()
		return 1
	}

	if err := c.innerRun(a, pa, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

func (c *ensurePoolHealthyRun) innerRun(a subcommands.Application, pa *posArgs, env subcommands.Env) error {
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

	if c.dryrun {
		fmt.Printf("DRYRUN: These changes are recommendations. Rerun without dryrun to apply changes.\n")
	}
	for _, m := range pa.Models {
		if err := c.ensurePoolForModel(ctx, ic, pa.Target, m); err != nil {
			return err
		}
	}
	return nil
}

func (c *ensurePoolHealthyRun) ensurePoolForModel(ctx context.Context, ic fleet.InventoryClient, target, model string) error {
	res, err := ic.EnsurePoolHealthy(
		ctx,
		&fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{Model: model},
			TargetPool:  target,
			SparePool:   c.spare,
		},
	)
	if err != nil {
		return errors.Annotate(err, "ensure pool for %s", model).Err()
	}
	c.printEnsurePoolHealthyResult(model, target, res)
	return nil
}

func (c *ensurePoolHealthyRun) printEnsurePoolHealthyResult(model, target string, res *fleet.EnsurePoolHealthyResponse) {
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "### Model: %s, Target: %s, Spare: %s\n", model, target, c.spare)
	tp := res.GetTargetPoolStatus()
	fmt.Fprintf(w, "New target pool status: %d/%d healthy\n", tp.HealthyCount, tp.Size)
	sp := res.GetSparePoolStatus()
	fmt.Fprintf(w, "New spare pool status: %d/%d healthy\n", sp.HealthyCount, sp.Size)
	if len(res.GetChanges()) > 0 {
		fmt.Fprintf(w, "\n")
		fmt.Fprintf(w, "Inventory changes:\n")
		for _, c := range res.GetChanges() {
			fmt.Fprintf(w, "  %s: %s --> %s\n", c.DutId, c.OldPool, c.NewPool)
		}
	}
	if len(res.GetFailures()) > 0 {
		fs := make([]string, 0, len(res.Failures))
		for _, f := range res.Failures {
			fs = append(fs, f.String())
		}
		fmt.Fprintf(w, "\n")
		fmt.Fprintf(w, "Failures encountered: %s\n", strings.Join(fs, ", "))
	}
	if res.GetUrl() != "" {
		fmt.Fprintf(w, "\n")
		fmt.Fprintf(w, "Inventory changes commited at: %s\n", res.GetUrl())
	}
	fmt.Fprintf(w, "\n")
}

func (*ensurePoolHealthyRun) parseArgs(args []string) (*posArgs, error) {
	if len(args) < 2 {
		return nil, fmt.Errorf("want at least 2 arguments, have %d", len(args))
	}
	return &posArgs{
		Target: args[0],
		Models: args[1:],
	}, nil
}
