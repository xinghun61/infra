// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
	"io"
	"sort"
	"text/tabwriter"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
)

// Inspect subcommand: Inspect a qscheduler pool.
var Inspect = &subcommands.Command{
	UsageLine: "inspect POOL_ID",
	ShortDesc: "Inspect a qscheduler pool",
	LongDesc:  "Inspect a qscheduler pool.",
	CommandRun: func() subcommands.CommandRun {
		c := &inspectRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.accounts, "accounts", false, "Show the account balances and policies.")
		c.Flags.BoolVar(&c.bots, "bots", false, "Show the bot summaries.")
		c.Flags.BoolVar(&c.tasks, "tasks", false, "Show the task summaries.")
		return c
	},
}

type inspectRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	accounts  bool
	bots      bool
	tasks     bool
}

func (c *inspectRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)

	if len(args) == 0 {
		fmt.Fprintf(a.GetErr(), "missing POOL_ID\n")
		c.Flags.Usage()
		return 1
	}

	if len(args) > 1 {
		fmt.Fprintf(a.GetErr(), "too many arguments\n")
		c.Flags.Usage()
		return 1
	}

	if flagCount([]bool{c.accounts, c.bots, c.tasks}) > 1 {
		fmt.Fprintf(a.GetErr(), "too many flags assigned\n")
		c.Flags.Usage()
		return 1
	}

	poolID := args[0]

	viewService, err := newViewClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to create qsview client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.InspectPoolRequest{
		PoolId: poolID,
	}

	resp, err := viewService.InspectPool(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to inspect scheduler, due to error: %s\n", err.Error())
		return 1
	}

	if c.accounts {
		printAccountTables(a.GetOut(), resp)
	} else if c.bots {
		printBotTables(a.GetOut(), resp)
	} else if c.tasks {
		printTaskTables(a.GetOut(), resp)
	} else {
		fmt.Println(proto.MarshalTextString(resp))
	}
	return 0
}

func flagCount(flags []bool) int {
	r := 0
	for _, flag := range flags {
		if flag {
			r++
		}
	}
	return r
}

type row []string

// print prints the row into tabWriter.
func (r row) print(tw *tabwriter.Writer) {
	for _, s := range r {
		fmt.Fprintf(tw, "%s\t", s)
	}
}

type table []row

// print prints the table into tabWriter.
func (t table) print(tw *tabwriter.Writer) {
	for _, r := range t {
		r.print(tw)
		fmt.Fprintln(tw)
	}
}

// sort alphabetically sorts the table by its first colmun.
func (t table) sort() {
	if len(t) <= 1 {
		return
	}
	sort.Slice(t, func(i, j int) bool { return t[i][0] < t[j][0] })
	return
}

// floatInsert inserts float slice to a row. If the size of the slice
// is less than l, it will append 0.0 instead.
func floatInsert(v []float32, l int, r row) row {
	for k := 0; k < l; k++ {
		if k >= len(v) {
			r = append(r, fmt.Sprintf("%.1f", 0.0))
			continue
		}
		r = append(r, fmt.Sprintf("%.1f", v[k]))
	}
	return r
}

func printAccountTables(w io.Writer, report *qscheduler.InspectPoolResponse) {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	printAccountBalancesTable(tw, report)
	printAccountRatesTable(tw, report)
	printAccountPoliciesTable(tw, report)
	tw.Flush()
}

func printAccountBalancesTable(tw *tabwriter.Writer, report *qscheduler.InspectPoolResponse) {
	fmt.Fprintln(tw, "Account Balance(bot seconds)")
	fmt.Fprintln(tw, "================================================================")
	header := row{"Account", "P0", "P1", "P2", "P3", "P4"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.AccountBalances))
	for account, balance := range report.GetAccountBalances() {
		r := make(row, 0, len(header))
		r = append(r, account)
		t = append(t, floatInsert(balance.GetValue(), len(header)-1, r))
	}
	t.sort()
	t.print(tw)
	fmt.Fprintln(tw)
	return
}

func printAccountRatesTable(tw *tabwriter.Writer, report *qscheduler.InspectPoolResponse) {
	fmt.Fprintln(tw, "Account Charge Rate(bot seconds per second)")
	fmt.Fprintln(tw, "================================================================")
	header := row{"Account", "P0", "P1", "P2", "P3", "P4"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.GetAccountConfigs()))
	for account, config := range report.GetAccountConfigs() {
		r := make(row, 0, len(header))
		r = append(r, account)
		t = append(t, floatInsert(config.GetChargeRate(), len(header)-1, r))
	}
	t.sort()
	t.print(tw)
	fmt.Fprintln(tw)
	return
}

func printAccountPoliciesTable(tw *tabwriter.Writer, report *qscheduler.InspectPoolResponse) {
	fmt.Fprintln(tw, "Account Policy")
	fmt.Fprintln(tw, "================================================================")
	header := row{"Account", "MaxChargeSec", "MaxFanout", "DisableFreeTasks"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.GetAccountConfigs()))
	for account, config := range report.GetAccountConfigs() {
		r := make(row, 0, len(header))
		r = append(r, []string{
			account,
			fmt.Sprintf("%.1f", config.GetMaxChargeSeconds()),
			fmt.Sprintf("%d", config.GetMaxFanout()),
			fmt.Sprintf("%t", config.GetDisableFreeTasks()),
		}...)
		t = append(t, r)
	}
	t.sort()
	t.print(tw)
	fmt.Fprintln(tw)
	return
}

func printBotTables(w io.Writer, report *qscheduler.InspectPoolResponse) {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	fmt.Fprintln(tw, "Bot Summary")
	fmt.Fprintln(tw, "================================================================")
	header := row{"IdleBot", "Age(Seconds)", "Dimensions"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.GetIdleBots()))
	for _, bot := range report.GetIdleBots() {
		if len(bot.Dimensions) > 0 {
			t = append(t, row{
				bot.Id,
				fmt.Sprintf("%d", bot.AgeSeconds),
				bot.Dimensions[0],
			})
			for i := 1; i < len(bot.Dimensions); i++ {
				t = append(t, row{
					"",
					"",
					bot.Dimensions[i],
				})
			}
			continue
		}
		t = append(t, row{
			bot.Id,
			fmt.Sprintf("%d", bot.AgeSeconds),
			"",
		})
	}
	t.print(tw)
	fmt.Fprintln(tw)
	return
}

func printTaskTables(w io.Writer, report *qscheduler.InspectPoolResponse) {
	tw := tabwriter.NewWriter(w, 0, 0, 2, ' ', 0)
	printRunningTaskTables(tw, report)
	printWaitingTaskTables(tw, report)
}

func printRunningTaskTables(tw *tabwriter.Writer, report *qscheduler.InspectPoolResponse) {
	fmt.Fprintln(tw, "Running Tasks")
	fmt.Fprintln(tw, "================================================================")
	header := row{"RequestId", "BotId", "Priority", "AccountId", "Age(Seconds)"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.GetRunningTasks()))
	for _, task := range report.GetRunningTasks() {
		t = append(t, row{
			task.GetId(),
			task.GetBotId(),
			fmt.Sprintf("%d", task.GetPriority()),
			task.GetAccountId(),
			fmt.Sprintf("%d", task.GetAgeSeconds()),
		})
	}
	t.sort()
	t.print(tw)
	fmt.Fprintln(tw)
	return
}

func printWaitingTaskTables(tw *tabwriter.Writer, report *qscheduler.InspectPoolResponse) {
	fmt.Fprintln(tw, "Waiting Tasks")
	fmt.Fprintln(tw, "================================================================")
	header := row{"RequestId", "AccountId", "Age(Seconds)"}
	header.print(tw)
	fmt.Fprintln(tw)
	t := make(table, 0, len(report.GetWaitingTasks()))
	for _, task := range report.GetWaitingTasks() {
		t = append(t, row{
			task.GetId(),
			task.GetAccountId(),
			fmt.Sprintf("%d", task.GetAgeSeconds()),
		})
	}
	t.sort()
	t.print(tw)
	fmt.Fprintln(tw)
	return
}
