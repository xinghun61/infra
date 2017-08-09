// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"os"
	"sync/atomic"
	"time"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"
)

func editCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit [options]",
		ShortDesc: "edits the userland of a JobDescription",
		LongDesc: `Allows common manipulations to a JobDescription.

Example:

led get-builder ... |
  led edit -d os=Linux -p something=[100] |
  led launch
`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEdit{}
			ret.logCfg.Level = logging.Info

			ret.Flags.Var(&ret.dimensions, "d",
				"(repeatable) override a dimension. This takes a parameter of `dimension=value`. "+
					"Providing an empty value will remove that dimension.")

			ret.Flags.Var(&ret.properties, "p",
				"(repeatable) override a recipe property. This takes a parameter of `property_name=json_value`. "+
					"Providing an empty json_value will remove that property.")

			ret.Flags.StringVar(&ret.recipeIsolate, "rbh", "",
				"override the recipe bundle `hash` (such as you might get from the isolate command).")

			ret.Flags.StringVar(&ret.recipeURL, "ru", "",
				"override the recipe repo `url` (if not using a bundle).")

			ret.Flags.StringVar(&ret.recipeRevision, "rr", "",
				"override the recipe repo `revision` (if not using a bundle).")

			ret.Flags.StringVar(&ret.recipeName, "r", "",
				"override the `recipe` to run.")

			ret.Flags.StringVar(&ret.swarmingHost, "S", "",
				"override the swarming `host` to launch the task on (i.e. chromium-swarm.appspot.com).")

			return ret
		},
	}
}

type cmdEdit struct {
	subcommands.CommandRunBase

	logCfg logging.Config

	recipeIsolate  string
	dimensions     stringmapflag.Value
	properties     stringmapflag.Value
	recipeURL      string
	recipeRevision string
	recipeName     string

	swarmingHost string
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
	return jd, errors.Annotate(err, "decoding JobDefinition").Err()
}

func editMode(ctx context.Context, cb func(jd *JobDefinition) error) error {
	jd, err := decodeJobDefinition(ctx)
	if err != nil {
		return err
	}

	if err = cb(jd); err != nil {
		return err
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(jd); err != nil {
		return errors.Annotate(err, "encoding JobDefinition").Err()
	}

	return nil
}

func (c *cmdEdit) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	err := editMode(ctx, func(jd *JobDefinition) error {
		ejd := jd.Edit()
		ejd.RecipeSource(c.recipeIsolate, c.recipeURL, c.recipeRevision)
		ejd.Dimensions(c.dimensions)
		ejd.Properties(c.properties)
		ejd.Recipe(c.recipeName)
		ejd.SwarmingHostname(c.swarmingHost)
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
