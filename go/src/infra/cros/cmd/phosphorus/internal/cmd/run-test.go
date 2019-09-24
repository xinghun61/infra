// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// RunTest subcommand: Run a test against one or multiple DUTs.
var RunTest = &subcommands.Command{
	UsageLine: "run-test",
	ShortDesc: "Run a test against one or multiple DUTs.",
	LongDesc: `Run a test against one or multiple DUTs.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &runTestRun{}
		return c
	},
}

type runTestRun struct {
	subcommands.CommandRunBase
}

func (c *runTestRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *runTestRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
