// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"
)

// EnsurePoolHealthy subcommand: Balance DUT pools
var EnsurePoolHealthy = &subcommands.Command{
	UsageLine: "ensure-pool-healthy [-dryrun] [-all-models] [-s spare] target [model...]",
	ShortDesc: "Ensure DUT pool is healthy",
	LongDesc: `
Ensure that given models' target pool contains healthy DUTs.
If needed, swap in healthy DUTs from spare pool.`,
	CommandRun: func() subcommands.CommandRun {
		c := &ensurePoolHealthyRun{}
		c.envFlags.Register(&c.Flags)

		c.Flags.BoolVar(&c.dryrun, "dryrun", false, "Dryrun mode -- do not commit inventory changes")
		c.Flags.BoolVar(&c.allModels, "all-models", false, "Ensure pool health for all known models")
		c.Flags.StringVar(&c.spare, "spare", "DUT_POOL_SUITES", "DUT pool to swap in healthy DUTs from")
		return c
	},
}

type ensurePoolHealthyRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	dryrun    bool
	allModels bool
	spare     string
}

type userError struct {
	error
}

func (c *ensurePoolHealthyRun) printError(err error) {
	fmt.Fprintf(os.Stderr, "%s\n\n", err)
	switch err.(type) {
	case userError:
		c.Flags.Usage()
	default:
		// Nothing more to say
	}
}

func (c *ensurePoolHealthyRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		c.printError(err)
		return 1
	}
	return 0
}

func (c *ensurePoolHealthyRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()

	target, err := c.getTargetPool(args)
	if err != nil {
		return nil
	}
	models, err := c.getModels(ctx, hc, args)
	if err != nil {
		return err
	}

	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})

	if c.dryrun {
		fmt.Printf("DRYRUN: These changes are recommendations. Rerun without dryrun to apply changes.\n")
	}
	for _, m := range models {
		if err := c.ensurePoolForModel(ctx, ic, target, m); err != nil {
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
	fmt.Fprintf(w, "New target pool status: %d/%d healthy\n", tp.GetHealthyCount(), tp.GetSize())
	sp := res.GetSparePoolStatus()
	fmt.Fprintf(w, "New spare pool status: %d/%d healthy\n", sp.GetHealthyCount(), sp.GetSize())
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

func (*ensurePoolHealthyRun) getTargetPool(args []string) (string, error) {
	if len(args) < 1 {
		return "", userError{errors.New("want at least 1 arguments, have none")}
	}
	return args[0], nil
}

func (c *ensurePoolHealthyRun) getModels(ctx context.Context, hc *http.Client, args []string) ([]string, error) {
	numModelPosArgs := len(args) - 1
	if c.allModels {
		if numModelPosArgs > 0 {
			return []string{}, userError{fmt.Errorf("want no model postional arguments with -all-models, got %d", numModelPosArgs)}
		}
		return c.getAllModels(ctx, hc)
	}

	if numModelPosArgs < 1 {
		return []string{}, userError{fmt.Errorf("want at least 1 model positional argument, have %d", numModelPosArgs)}
	}
	return args[1:], nil
}

func (c *ensurePoolHealthyRun) getAllModels(ctx context.Context, hc *http.Client) ([]string, error) {
	// TODO(pprabhu) Consider implementing an RPC directly to ensure pool health
	// for all models.
	e := c.envFlags.Env()
	tc := fleet.NewTrackerPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})
	res, err := tc.SummarizeBots(ctx, &fleet.SummarizeBotsRequest{})
	if err != nil {
		return []string{}, err
	}
	r := compileInventoryReport(res.GetBots())
	return modelsFromInventory(r.models), nil
}

func modelsFromInventory(ics []*inventoryCount) []string {
	ms := make([]string, 0, len(ics))
	for _, ic := range ics {
		ms = append(ms, ic.name)
	}
	return ms
}
