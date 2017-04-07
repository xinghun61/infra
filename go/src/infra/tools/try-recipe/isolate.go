// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
)

func isolateCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		// TODO(iannucci): implement
		CommandRun: func() subcommands.CommandRun {
			ret := &cmdIsolate{}
			ret.authFlags.Register(&ret.Flags, authOpts)
			return ret
		},
	}
}

type cmdIsolate struct {
	subcommands.CommandRunBase

	authFlags authcli.Flags
}

func (c *cmdIsolate) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	return 0
}
