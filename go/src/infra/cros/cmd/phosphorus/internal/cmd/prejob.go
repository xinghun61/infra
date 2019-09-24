// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// Prejob subcommand: Run a prejob (e.g. provision) against a DUT.
var Prejob = &subcommands.Command{
	UsageLine: "prejob",
	ShortDesc: "Run a prejob against a DUT.",
	LongDesc: `Run a prejob against a DUT.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &prejobRun{}
		return c
	},
}

type prejobRun struct {
	subcommands.CommandRunBase
}

func (c *prejobRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *prejobRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
