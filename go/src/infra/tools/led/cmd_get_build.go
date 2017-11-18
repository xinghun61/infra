// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"strconv"
	"strings"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/client/authcli"
	buildbucket "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry/transient"
)

func getBuildCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "get-build <buildbucket_build_id>",
		ShortDesc: "obtain a JobDefinition from a buildbucket build",
		LongDesc: `Obtains the build's definition from buildbucket and produces a JobDefinition.

buildbucket_build_id can be specified with "b" prefix like b8962624445013664976,
which is useful when copying it from ci.chromium.org URL.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdGetBuild{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.StringVar(&ret.bbHost, "B", bbHostDefault,
				"The buildbucket hostname to grab the definition from.")

			ret.Flags.BoolVar(&ret.pinMachine, "pin-machine", false,
				"Pin the dimensions of the JobDefinition to run on the same machine.")

			return ret
		},
	}
}

type cmdGetBuild struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	bbHost     string
	pinMachine bool
	buildID    int64
}

func (c *cmdGetBuild) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) != 1 {
		err = errors.Reason("unexpected positional arguments: %q", args).Err()
		return
	}
	if err = validateHost(c.bbHost); err != nil {
		err = errors.Annotate(err, "").Err()
		return
	}

	buildIdStr := args[0]
	if strings.HasPrefix(buildIdStr, "b") {
		// Milo URL structure prefixes buildbucket builds id with "b".
		buildIdStr = args[0][1:]
	}
	if c.buildID, err = strconv.ParseInt(buildIdStr, 10, 64); err != nil {
		err = errors.Annotate(err, "bad <buildbucket_build_id>").Err()
		return
	}

	return c.authFlags.Options()
}

func (c *cmdGetBuild) grabBuildDefinition(ctx context.Context, authOpts auth.Options) error {
	logging.Infof(ctx, "getting build definition")
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		return err
	}
	bbucket, err := buildbucket.New(authClient)
	if err != nil {
		return err
	}
	bbucket.BasePath = fmt.Sprintf("https://%s/api/buildbucket/v1/", c.bbHost)

	answer, err := bbucket.Get(c.buildID).Do()
	if err != nil {
		return transient.Tag.Apply(err)
	}
	if answer.Error != nil {
		return errors.New(answer.Error.Reason)
	}
	logging.Infof(ctx, "getting build definition: done")

	swarmingTaskID := ""
	swarmingHostname := ""
	for _, t := range answer.Build.Tags {
		toks := strings.SplitN(t, ":", 2)
		if len(toks) != 2 {
			continue
		}
		switch toks[0] {
		case "swarming_task_id":
			swarmingTaskID = toks[1]
		case "swarming_hostname":
			swarmingHostname = toks[1]
		}
		if swarmingTaskID != "" && swarmingHostname != "" {
			break
		}
	}

	if swarmingTaskID == "" {
		return errors.New("unable to find swarming task ID on buildbucket task")
	}
	if swarmingHostname == "" {
		return errors.New("unable to find swarming hostname on buildbucket task")
	}

	return GetFromSwarmingTask(ctx, authOpts, swarmingHostname, swarmingTaskID, c.pinMachine)
}

func (c *cmdGetBuild) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	if err := c.grabBuildDefinition(ctx, authOpts); err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
