// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"go.chromium.org/luci/common/flag"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/cli"
)

type publishRun struct {
	baseRun
	messageString string
	messageFile   string
	attributes    map[string]string
}

// CmdPublish describes the subcommand flags for publishing messages
var CmdPublish = &subcommands.Command{
	UsageLine: "publish -project [PROJECT] -topic [TOPIC] [OPTIONS]",
	ShortDesc: "publish a message to a topic",
	CommandRun: func() subcommands.CommandRun {
		c := &publishRun{}
		c.registerCommonFlags(&c.Flags)
		c.Flags.StringVar(&c.messageFile, "file", "", "path to file to send as message")
		c.Flags.Var(flag.JSONMap(&c.attributes), "attributes", "map of attributes to add to the message")
		return c
	},
}

func (c *publishRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	_ = cli.GetContext(a, c, env)
	return 0
}
