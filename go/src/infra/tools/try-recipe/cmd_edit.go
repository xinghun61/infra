// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"os"
	"sync/atomic"
	"time"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	"github.com/luci/luci-go/common/logging"
)

func editCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit [options]",
		ShortDesc: "edits a JobDescription",
		LongDesc: `Allows common manipulations to a JobDescription.

Example:

try-recipe get-builder ... |
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

	swarmingServer string
}

func (e *editFlags) register(fs *flag.FlagSet) {
	fs.Var(&e.dimensions, "d",
		"(repeatable) override a dimension. This takes a parameter of `dimension=value`. "+
			"Providing an empty value will remove that dimension.")

	fs.Var(&e.properties, "p",
		"(repeatable) override a recipe property. This takes a parameter of `property_name=json_value`. "+
			"Providing an empty json_value will remove that property.")

	fs.Var(&e.environment, "e",
		"(repeatable) override an environment variable. This takes a parameter of `env_var=value`. "+
			"Providing an empty value will remove that envvar.")

	fs.StringVar(&e.recipeIsolate, "rbh", "",
		"override the recipe bundle `hash` (such as you might get from the isolate command).")

	fs.StringVar(&e.swarmingServer, "S", "",
		"override the swarming `server` to launch the task on.")
}

func (e *editFlags) Edit(jd *JobDefinition) (*JobDefinition, error) {
	ejd := jd.Edit()
	ejd.RecipeSource(e.recipeIsolate)
	ejd.Dimensions(e.dimensions)
	ejd.Properties(e.properties)
	ejd.Env(e.environment)
	ejd.SwarmingServer(e.swarmingServer)
	return ejd.Finalize()
}

func decodeJobDefinition(ctx context.Context) (*JobDefinition, error) {
	done := uint32(0)
	go func() {
		time.Sleep(time.Second)
		if atomic.LoadUint32(&done) == 0 {
			logging.Warningf(ctx, "waiting for JobDefinition on stdin...")
		}
	}()

	jd := &JobDefinition{}
	err := json.NewDecoder(os.Stdin).Decode(jd)
	atomic.StoreUint32(&done, 1)
	return jd, errors.Annotate(err).Reason("decoding JobDefinition").Err()
}

func editMode(ctx context.Context, cb func(jd *JobDefinition) (*JobDefinition, error)) error {
	jd, err := decodeJobDefinition(ctx)
	if err != nil {
		return err
	}

	jd, err = cb(jd)
	if err != nil {
		return err
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(jd); err != nil {
		return errors.Annotate(err).Reason("encoding JobDefinition").Err()
	}

	return nil
}

func (c *cmdEdit) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	if err := editMode(ctx, c.editFlags.Edit); err != nil {
		logging.WithError(err).Errorf(ctx, "fatal")
		return 1
	}

	return 0
}
