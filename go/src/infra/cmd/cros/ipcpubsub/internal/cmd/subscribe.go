// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"

	"go.chromium.org/luci/common/flag"

	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
)

type subscribeRun struct {
	baseRun
	attributes   map[string]string
	messageCount int
	subName      string
	timeout      time.Duration
	outputDir    string
}

const pubSubCompatibleTimeFormat = "2006-01-02-15-04-05.000000000"

// CmdSubscribe describes the subcommand flags for subscribing to messages
var CmdSubscribe = &subcommands.Command{
	UsageLine: "subscribe -project [PROJECT] -topic [TOPIC] -output [PATH/TO/OUTPUT/DIR] [OPTIONS]",
	ShortDesc: "subscribe to a filtered topic",
	CommandRun: func() subcommands.CommandRun {
		c := &subscribeRun{}
		c.registerCommonFlags(&c.Flags)
		c.Flags.Var(flag.JSONMap(&c.attributes), "attributes", "map of attributes to filter for")
		c.Flags.IntVar(&c.messageCount, "count", 1, "number of messages to read before returning")
		c.Flags.StringVar(&c.outputDir, "output", "", "path to directory to store output")
		c.Flags.StringVar(&c.subName, "sub-name", "", "name of subscription: must be 3-255 characters, start with a letter, and composed of alphanumerics and -_.~+% only")
		c.Flags.DurationVar(&c.timeout, "timeout", time.Hour, "timeout to stop waiting, ex. 10s, 5m, 1h30m")
		return c
	},
}

func (c *subscribeRun) validateArgs(ctx context.Context, a subcommands.Application, args []string, env subcommands.Env) error {
	if c.messageCount < 1 {
		return errors.Reason("message-count must be >0").Err()
	}
	if c.subName == "" {
		return errors.Reason("subscription name is required").Err()
	}
	minTimeout := 10 * time.Second
	if c.timeout < minTimeout {
		return errors.Reason("timeout must be >= 10s").Err()
	}
	return nil
}

func (c *subscribeRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if err := c.validateArgs(ctx, a, args, env); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}
	return 0
}
