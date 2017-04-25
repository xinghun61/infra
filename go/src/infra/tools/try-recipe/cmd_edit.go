// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"os"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	"github.com/luci/luci-go/common/logging"
)

func editCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit [options]",
		ShortDesc: "Consumes a JobDescription on stdin, edits it, and emits it on stdout.",
		LongDesc: `Allows common manipulations to a JobDescription. Example:

		try-recipe builder-def ... |
			try-recipe edit -d os=Linux -p something=[100] |
			try-recipe launch
		`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEdit{}
			ret.logCfg.Level = logging.Info

			ret.editFlags.register(&ret.Flags)

			return ret
		},
	}
}

type cmdEdit struct {
	subcommands.CommandRunBase

	logCfg logging.Config

	editFlags editFlags
}

type editFlags struct {
	recipeIsolate string
	dimensions    stringmapflag.Value
	properties    stringmapflag.Value
	environment   stringmapflag.Value
}

func (e *editFlags) register(fs *flag.FlagSet) {
	fs.Var(&e.dimensions, "d", "shorthand for 'dimension'")
	fs.Var(&e.dimensions, "dimension",
		("override a dimension. This takes a parameter of dimension=value. " +
			"Providing an empty value will remove that dimension."))

	fs.Var(&e.properties, "p", "shorthand for 'property'")
	fs.Var(&e.properties, "property",
		("override a recipe property. This takes a parameter of property_name=json_value. " +
			"Providing an empty json_value will remove that property."))

	fs.Var(&e.environment, "e", "shorthand for 'env'")
	fs.Var(&e.environment, "env",
		("override an environment. This takes a parameter of env_var=value. " +
			"Providing an empty value will remove that envvar."))

	fs.StringVar(&e.recipeIsolate, "r", "", "shorthand for 'recipe'")
	fs.StringVar(&e.recipeIsolate, "recipe", "", "override the recipe isolate hash.")
}

func (e *editFlags) Edit(jd *JobDefinition) (*JobDefinition, error) {
	return jd.Edit(e.dimensions, e.properties, e.environment, e.recipeIsolate)
}

func (c *cmdEdit) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	jd := &JobDefinition{}
	if err := json.NewDecoder(os.Stdin).Decode(jd); err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	jd, err := c.editFlags.Edit(jd)
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
