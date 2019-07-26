// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// Load subcommand: Gather DUT labels and attributes into a host info file.
var Load = &subcommands.Command{
	UsageLine: "load",
	ShortDesc: "Gather DUT labels and attributes into a host info file.",
	LongDesc: `Gather DUT labels and attributes into a host info file.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &loadRun{}
		return c
	},
}

type loadRun struct {
	subcommands.CommandRunBase
}

func (c *loadRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *loadRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
