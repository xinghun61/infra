// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"
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
	"infra/libs/skylab/swarming"
)

// Diagnose subcommand: Diagnose DUT status.
var Diagnose = &subcommands.Command{
	UsageLine: "diagnose [-dev] [-short] [HOST...]",
	ShortDesc: "diagnose DUT status",
	LongDesc: `Diagnose DUT status.

This prints the current status of DUTs and a list of tasks that show
how the DUTs got into that state.

This is the equivalent of dut-status in Autotest.`,
	CommandRun: func() subcommands.CommandRun {
		c := &diagnoseRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.short, "short", false, "Print short diagnosis.")
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
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *diagnoseRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
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
	tw := tabwriter.NewWriter(a.GetOut(), 0, 0, 3, ' ', 0)
	if c.short {
		printBotDiagnosisShort(tw, e, bots)
	} else {
		ds := prepareDiagnosis(bots)
		printBotDiagnosis(tw, e, ds)
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
			url = swarming.TaskURL(e.SwarmingService, ds[0].GetId())
			ts = getTaskTimeString(ds[0])
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", b.GetDimensions().GetDutName(), b.GetDutState(), ts, url)
	}
}

type diagnosis struct {
	summary     *fleet.BotSummary
	statusSince time.Time
}

func prepareDiagnosis(bots []*fleet.BotSummary) []diagnosis {
	ds := make([]diagnosis, len(bots))
	for i, b := range bots {
		ds[i].summary = b
		if b.GetDutState() == fleet.DutState_RepairFailed {
			ds[i].statusSince = getFirstFailedTime(b)
		}
	}
	return ds
}

// getFirstFailedTime returns the time the bot first failed.  If the
// time cannot be determined, returns the zero time value.
func getFirstFailedTime(b *fleet.BotSummary) time.Time {
	for _, t := range b.GetDiagnosis() {
		if !isInitialFailureTask(t) {
			continue
		}
		tm, err := ptypes.Timestamp(t.GetStartedTs())
		if err != nil {
			return time.Time{}
		}
		return tm
	}
	return time.Time{}
}

// isInitialFailureTask returns true if the task transitioned the bot
// state to failed.
func isInitialFailureTask(t *fleet.Task) bool {
	if t.GetStateAfter() != fleet.DutState_RepairFailed {
		return false
	}
	return t.GetStateBefore() != fleet.DutState_RepairFailed
}

func printBotDiagnosis(w io.Writer, e site.Environment, ds []diagnosis) {
	for _, d := range ds {
		b := d.summary
		var sinceMsg string
		if !d.statusSince.IsZero() {
			sinceMsg = fmt.Sprintf("since %s", d.statusSince.Local().Format(time.RFC1123Z))
		}
		fmt.Fprintf(w, "---\t%s\t%s\t%s\t\t\n", b.GetDimensions().GetDutName(), b.GetDutState(), sinceMsg)
		for _, t := range b.GetDiagnosis() {
			printDiagnosisTask(w, e, t)
		}
		fmt.Fprintln(w)
	}
}

func printDiagnosisTask(w io.Writer, e site.Environment, t *fleet.Task) {
	ts := getTaskTimeString(t)
	fmt.Fprintf(w, "\t%s\t%s <- %s\t%s\t%s\t\n",
		t.GetName(), t.GetStateAfter(), t.GetStateBefore(), ts,
		swarming.TaskURL(e.SwarmingService, t.GetId()))
}

func getTaskTimeString(t *fleet.Task) string {
	if tm, err := ptypes.Timestamp(t.GetStartedTs()); err == nil {
		return tm.Local().Format(time.RFC1123Z)
	}
	return "Unknown"
}
