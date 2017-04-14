// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"os"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	"github.com/luci/luci-go/common/logging"
)

func builderDefinitionCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "builder-def -B bucket_name -builder builder_name [-recipes <hash>] [-d dimension=value]*",
		ShortDesc: "Pulls a builder definition from buildbucket and prints a swarming task definition.",
		LongDesc: `Obtains the builder definition from buildbucket and renders a stanadlone
		swarming task definition. If -recipes is supplied, the rendered definition will
		be setup to run that recipe bundle.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdBuilderDefinition{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.StringVar(&ret.recipesHash, "recipes", "RECIPE_HASH", "a value for the recipe isolate hash.")
			ret.Flags.Var(&ret.dimensions, "d", "set a swarming dimension. Will override buildbucket's value, if any.")
			return ret
		},
	}
}

type cmdBuilderDefinition struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	recipesHash string
	dimensions  stringmapflag.Value
}

func (c *cmdBuilderDefinition) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %(args)q").D("args", args).Err()
		return
	}

	for k, v := range c.dimensions {
		if k == "" {
			err = errors.New("dimension has empty name")
			return
		}
		if v == "" {
			err = errors.Reason("dimension %(key)q has empty value").D("dimension", k).Err()
			return
		}
	}

	return c.authFlags.Options()
}

func (c *cmdBuilderDefinition) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	_, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s", err)
		fmt.Fprintln(os.Stderr)
		subcommands.CmdHelp.CommandRun().Run(a, args, env)
		return 1
	}

	panic("not implemented")
}
