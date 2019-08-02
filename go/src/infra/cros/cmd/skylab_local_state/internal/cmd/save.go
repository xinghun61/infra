// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// Save subcommand: Update the bot state json file.
func Save() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "save",
		ShortDesc: "Update the bot state json file.",
		LongDesc: `Update the bot state json file.

	Placeholder only, not yet implemented.`,
		CommandRun: func() subcommands.CommandRun {
			c := &saveRun{}
			return c
		},
	}
}

type saveRun struct {
	subcommands.CommandRunBase
}

func (c *saveRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *saveRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
