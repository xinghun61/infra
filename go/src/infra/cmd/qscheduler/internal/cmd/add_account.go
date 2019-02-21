// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"
	"strconv"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/flag"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
	"infra/qscheduler/qslib/protos"
)

// AddAccount subcommand: add an account.
var AddAccount = &subcommands.Command{
	UsageLine: "add-account [-rate RATE...] [-charge-time CHARGE_TIME] [-fanout FANOUT] POOL_ID ACCOUNT_ID",
	ShortDesc: "Add a quota account",
	LongDesc:  "Add a quota account",
	CommandRun: func() subcommands.CommandRun {
		c := &addAccountRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.Var(flag.StringSlice(&c.chargeRates), "rate", "Quota recharge rate for a given priority level. "+
			"May be specified multiple times, to specify charge rate at P0, P1, P2, ...")
		c.Flags.Float64Var(&c.chargeTime, "charge-time", 0,
			"Maximum amount of time (seconds) for which the account can accumulate quota.")
		c.Flags.IntVar(&c.fanout, "fanout", 0, "Maximum number of concurrent tasks that account will pay for.")
		return c
	},
}

type addAccountRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	chargeRates []string
	chargeTime  float64
	fanout      int
}

func (c *addAccountRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) < 2 {
		fmt.Fprintf(os.Stderr, "not enough arguments\n")
		c.Flags.Usage()
		return 1
	}

	if len(args) > 2 {
		fmt.Fprintf(os.Stderr, "too many arguments\n")
		c.Flags.Usage()
		return 1
	}

	poolID := args[0]
	accountID := args[1]

	chargeRateFloats := make([]float32, len(c.chargeRates))
	for i, c := range c.chargeRates {
		f, err := strconv.ParseFloat(c, 32)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Invalid charge rate: %s\n", err.Error())
			return 1
		}
		chargeRateFloats[i] = float32(f)
	}

	ctx := cli.GetContext(a, c, env)

	adminClient, err := newAdminClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to create qsadmin client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.CreateAccountRequest{
		AccountId: accountID,
		PoolId:    poolID,
		Config: &protos.AccountConfig{
			ChargeRate:       chargeRateFloats,
			MaxChargeSeconds: float32(c.chargeTime),
			MaxFanout:        int32(c.fanout),
		},
	}

	_, err = adminClient.CreateAccount(ctx, req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to add account, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Printf("Added account %s to scheduler %s.\n", accountID, poolID)
	return 0
}
