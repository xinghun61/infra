// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"github.com/maruel/subcommands"
)

var subcommandIsolate = &subcommands.Command{
	// TODO(iannucci): implement
	CommandRun: func() subcommands.CommandRun {
		return &cmdIsolate{}
	},
}

type cmdIsolate struct {
	subcommands.CommandRunBase
}

func (c *cmdIsolate) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	return 0
}
