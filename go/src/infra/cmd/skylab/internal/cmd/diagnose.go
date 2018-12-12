// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"
	"os"
	"text/tabwriter"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
)

// Diagnose subcommand: Diagnose DUT status.
var Diagnose = &subcommands.Command{
	UsageLine: "diagnose [HOST...]",
	ShortDesc: "Diagnose DUT status",
	LongDesc:  "Diagnose DUT status.",
	CommandRun: func() subcommands.CommandRun {
		c := &diagnoseRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type diagnoseRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *diagnoseRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

func (c *diagnoseRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := httpClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to get auth options").Err()
	}
	e := c.envFlags.Env()
	tc := fleet.NewTrackerPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})
	bots, err := summarizeBots(ctx, tc, args)
	if err != nil {
		return err
	}
	tw := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)
	printBotDiagnosis(tw, e, bots)
	_ = tw.Flush()
	return nil
}

// summarizeBots calls SummarizeBots using DUT IDs.
func summarizeBots(ctx context.Context, c fleet.TrackerClient, dutNames []string) ([]*fleet.BotSummary, error) {
	req := fleet.SummarizeBotsRequest{}
	for _, n := range dutNames {
		req.Selectors = append(req.Selectors, &fleet.BotSelector{
			Dimensions: &fleet.BotDimensions{DutName: n},
		})
	}
	res, err := c.SummarizeBots(ctx, &req)
	if err != nil {
		return nil, errors.Annotate(err, "failed to call SummarizeBots").Err()
	}
	return res.GetBots(), nil
}

func printBotDiagnosis(w io.Writer, e site.Environment, bots []*fleet.BotSummary) {
	for _, b := range bots {
		fmt.Fprintf(w, "---\t%s\t%s\t%s\t\n", b.GetDimensions().GetDutName(), b.GetDutId(), b.GetDutState())
		for _, t := range b.Diagnosis {
			printDiagnosisTask(w, e, t)
		}
		fmt.Fprintln(w)
	}
}

func printDiagnosisTask(w io.Writer, e site.Environment, t *fleet.Task) {
	var ts string
	if tm, err := ptypes.Timestamp(t.GetStartedTs()); err == nil {
		ts = tm.Format(time.RFC1123Z)
	} else {
		ts = "Unknown"
	}
	fmt.Fprintf(w, "\t%s\t%s\t%s -> %s\t%s\t\n",
		t.GetName(), ts, t.GetStateBefore(), t.GetStateAfter(),
		swarmingTaskURL(e, t.GetId()))
}
