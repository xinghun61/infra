// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"

	"github.com/golang/protobuf/ptypes/wrappers"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/flag"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

// ModAccount subcommand: add an account.
var ModAccount = &subcommands.Command{
	UsageLine: "mod-account [-rate RATE...] [-charge-time CHARGE_TIME] [-fanout FANOUT] POOL_ID ACCOUNT_ID",
	ShortDesc: "Modify a quota account",
	LongDesc:  "Modify a quota account. Values that are unspecified will not be modified.",
	CommandRun: func() subcommands.CommandRun {
		c := &modAccountRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.Var(flag.StringSlice(&c.chargeRates), "rate", "Quota recharge rate for a given priority level. "+
			"May be specified multiple times, to specify charge rate at P0, P1, P2, etc. If specified, overwrites "+
			"the full charge-rate vector.")
		c.Flags.Var(nullableFloat32Value(&c.chargeTime), "charge-time",
			"Maximum amount of time (seconds) for which the account can accumulate quota.")
		c.Flags.Var(nullableInt32Value(&c.fanout), "fanout", "Maximum number of concurrent tasks that account will pay for.")
		c.Flags.Var(nullableBoolValue(&c.disableFreeTasks), "disable-free-tasks", "Disallow the account from running free tasks.")
		c.Flags.BoolVar(&c.resetBalance, "reset-balance", false, "Reset the account's balance to 0.")
		return c
	},
}

type modAccountRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags

	chargeRates      []string
	chargeTime       *float32
	fanout           *int32
	disableFreeTasks *bool
	resetBalance     bool
}

// validate validates command line arguments.
func (c *modAccountRun) validate(args []string) error {
	if len(args) < 2 {
		return errors.New("not enough arguments")
	}

	if len(args) > 2 {
		return errors.New("too many arguments")
	}

	return nil
}

func (c *modAccountRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validate(args); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}

	poolID := args[0]
	accountID := args[1]

	chargeRateFloats, err := toFloats(c.chargeRates)
	if err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		return 1
	}

	ctx := cli.GetContext(a, c, env)

	adminClient, err := newAdminClient(ctx, &c.authFlags, &c.envFlags)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to create qsadmin client, due to error: %s\n", err.Error())
		return 1
	}

	req := &qscheduler.ModAccountRequest{
		AccountId:    accountID,
		PoolId:       poolID,
		ResetBalance: c.resetBalance,
	}

	if c.fanout != nil {
		req.MaxFanout = &wrappers.Int32Value{Value: *c.fanout}
	}
	if c.chargeTime != nil {
		req.MaxChargeSeconds = &wrappers.FloatValue{Value: *c.chargeTime}
	}
	if c.disableFreeTasks != nil {
		req.DisableFreeTasks = &wrappers.BoolValue{Value: *c.disableFreeTasks}
	}
	if len(chargeRateFloats) > 0 {
		req.ChargeRate = chargeRateFloats
	}

	_, err = adminClient.ModAccount(ctx, req)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "qscheduler: Unable to modify account, due to error: %s\n", err.Error())
		return 1
	}

	fmt.Fprintf(a.GetOut(), "qscheduler: Modified account %s in scheduler %s.\n", accountID, poolID)
	return 0
}
