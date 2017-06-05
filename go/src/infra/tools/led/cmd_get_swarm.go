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
	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
)

func getSwarmCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "get-swarm <swarm task id>",
		ShortDesc: "obtain a JobDefinition from a swarming task",
		LongDesc:  `Obtains the task definition from swarming and produce a JobDefinition.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdGetSwarm{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.StringVar(&ret.swarmingHost, "S", "chromium-swarm.appspot.com",
				"the swarming `host` to get the task from.")
			return ret
		},
	}
}

type cmdGetSwarm struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	taskID       string
	swarmingHost string
}

func (c *cmdGetSwarm) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) != 1 {
		err = errors.Reason("expected 1 positional argument: %(args)q").D("args", args).Err()
		return
	}
	c.taskID = args[0]

	if err = validateHost(c.swarmingHost); err != nil {
		err = errors.Annotate(err).Reason("SwarmingHostname").Err()
		return
	}

	return c.authFlags.Options()
}

func (c *cmdGetSwarm) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s", err)
		fmt.Fprintln(os.Stderr)
		subcommands.CmdHelp.CommandRun().Run(a, []string{"get-swarm"}, env)
		return 1
	}

	logging.Infof(ctx, "getting task definition")
	_, _, swarm, err := newSwarmClient(ctx, authOpts, c.swarmingHost)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	req, err := swarm.Task.Request(c.taskID).Do()
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	jd, err := JobDefinitionFromNewTaskRequest(&swarming.SwarmingRpcsNewTaskRequest{
		Name:           req.Name,
		ExpirationSecs: req.ExpirationSecs,
		Priority:       req.Priority,
		Properties:     req.Properties,
		// don't wan't these or some random person/service will get notified :)
		//PubsubTopic:    req.PubsubTopic,
		//PubsubUserdata: req.PubsubUserdata,
		Tags: req.Tags,
		User: req.User,
		//ServiceAccount: req.ServiceAccount,
	})
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}
	jd.SwarmingHostname = c.swarmingHost

	logging.Infof(ctx, "getting task definition: done")

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(jd); err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	return 0
}
