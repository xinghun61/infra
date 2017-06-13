// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringlistflag"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	"github.com/luci/luci-go/common/logging"
)

func editSystemCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit-system [options]",
		ShortDesc: "edits the systemland of a JobDescription",
		LongDesc:  `Allows manipulations of the 'system' data in a JobDescription.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEditSystem{}
			ret.logCfg.Level = logging.Info

			ret.Flags.Var(&ret.environment, "e",
				"(repeatable) override an environment variable. This takes a parameter of `env_var=value`. "+
					"Providing an empty value will remove that envvar.")

			ret.Flags.Var(&ret.cipdPackages, "cp",
				"(repeatable) override a cipd package. This takes a parameter of `[subdir:]pkgname=version`. "+
					"Using an empty version will remove the package. The subdir is optional and defaults to '.'.")

			ret.Flags.Var(&ret.prefixPathEnv, "ppe",
				"(repeatable) override a -prefix-path-env entry. Using a value like '!value' will remove a path entry.")

			return ret
		},
	}
}

type cmdEditSystem struct {
	subcommands.CommandRunBase

	logCfg logging.Config

	environment   stringmapflag.Value
	cipdPackages  stringmapflag.Value
	prefixPathEnv stringlistflag.Flag
}

func (c *cmdEditSystem) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	err := editMode(ctx, func(jd *JobDefinition) error {
		ejd := jd.Edit()
		ejd.Env(c.environment)
		ejd.CipdPkgs(c.cipdPackages)
		ejd.PrefixPathEnv(c.prefixPathEnv)
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
