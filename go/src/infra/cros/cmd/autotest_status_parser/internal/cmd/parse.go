// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// Parse subcommand: Extract test case results from status.log.
var Parse = &subcommands.Command{
	UsageLine: "parse",
	ShortDesc: "Extract test case results from status.log.",
	LongDesc: `Extract test case results from status.log.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &parseRun{}
		return c
	},
}

type parseRun struct {
	subcommands.CommandRunBase
}

func (c *parseRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *parseRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
