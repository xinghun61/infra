// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"os"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
)

const bbServerDefault = "https://cr-buildbucket.appspot.com"

func builderDefinitionCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "builder-def -B bucket_name -builder builder_name [-recipes <hash>] [-d dimension=value]*",
		ShortDesc: "Pulls a builder definition from buildbucket and prints a swarming task definition.",
		LongDesc: `Obtains the builder definition from buildbucket and prints a modified
		version of it as a JobDefinition.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdBuilderDefinition{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.StringVar(&ret.bucket, "B", "", "The bucket to grab from.")
			ret.Flags.StringVar(&ret.builder, "builder", "", "The builder to grab from.")

			ret.Flags.StringVar(&ret.bbServer, "bbserver", bbServerDefault, "The buildbucket server to grab the definition from.")
			return ret
		},
	}
}

type cmdBuilderDefinition struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	bbServer string
	bucket   string
	builder  string
}

func (c *cmdBuilderDefinition) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %(args)q").D("args", args).Err()
		return
	}
	return c.authFlags.Options()
}

func (c *cmdBuilderDefinition) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s", err)
		fmt.Fprintln(os.Stderr)
		subcommands.CmdHelp.CommandRun().Run(a, args, env)
		return 1
	}

	jd, err := grabBuilderDefinition(ctx, c.bbServer, c.bucket, c.builder, authOpts)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(jd); err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	return 0
}
