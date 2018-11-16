// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
)

// BalancePool subcommand: Balance DUT pools
var BalancePool = &subcommands.Command{
	UsageLine: "balance-pool [-dryrun]",
	ShortDesc: "Balance DUT pools",
	LongDesc:  "Balance DUT pools.",
	CommandRun: func() subcommands.CommandRun {
		c := &balancePoolRun{}
		c.authFlags.Register(&c.Flags, auth.Options{})
		c.Flags.BoolVar(&c.f, "foo", false, "foo")
		return c
	},
}

type balancePoolRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags

	f bool
}

func (c *balancePoolRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	fmt.Printf("Not implemented yet")
	// TODO(ayatane): Implement this.
	return 1
}
