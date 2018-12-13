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
	UsageLine: "diagnose [-dev] [-short] [HOST...]",
	ShortDesc: "Diagnose DUT status",
	LongDesc:  "Diagnose DUT status.",
	CommandRun: func() subcommands.CommandRun {
		c := &diagnoseRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.short, "short", false, "Print short diagnosis")
		return c
	},
}

type diagnoseRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	short bool
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
	if c.short {
		printBotDiagnosisShort(tw, e, bots)
	} else {
		printBotDiagnosis(tw, e, bots)
	}
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

func printBotDiagnosisShort(w io.Writer, e site.Environment, bots []*fleet.BotSummary) {
	for _, b := range bots {
		var url string
		ts := "Unknown"
		if ds := b.GetDiagnosis(); len(ds) > 0 {
			url = swarmingTaskURL(e, ds[0].GetId())
			ts = getTaskTimeString(ds[0])
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", b.GetDimensions().GetDutName(), b.GetDutState(), ts, url)
	}
}

func printBotDiagnosis(w io.Writer, e site.Environment, bots []*fleet.BotSummary) {
	for _, b := range bots {
		fmt.Fprintf(w, "---\t%s\t%s\t%s\t\n", b.GetDimensions().GetDutName(), b.GetDutId(), b.GetDutState())
		for _, t := range b.GetDiagnosis() {
			printDiagnosisTask(w, e, t)
		}
		fmt.Fprintln(w)
	}
}

func printDiagnosisTask(w io.Writer, e site.Environment, t *fleet.Task) {
	ts := getTaskTimeString(t)
	fmt.Fprintf(w, "\t%s\t%s\t%s -> %s\t%s\t\n",
		t.GetName(), ts, t.GetStateBefore(), t.GetStateAfter(),
		swarmingTaskURL(e, t.GetId()))
}

func getTaskTimeString(t *fleet.Task) string {
	if tm, err := ptypes.Timestamp(t.GetStartedTs()); err == nil {
		return tm.Format(time.RFC1123Z)
	}
	return "Unknown"
}
