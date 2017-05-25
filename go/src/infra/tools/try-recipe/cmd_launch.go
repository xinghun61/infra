// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/gcloud/googleoauth"
	"github.com/luci/luci-go/common/logging"
)

func launchCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "launch",
		ShortDesc: "launches a JobDefinition on swarming",

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdLaunch{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.BoolVar(&ret.dump, "dump", false, "dump swarming task to stdout instead of running it.")

			return ret
		},
	}
}

type cmdLaunch struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	dump bool
}

func (c *cmdLaunch) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %(args)q").D("args", args).Err()
		return
	}
	return c.authFlags.Options()
}

func (c *cmdLaunch) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s", err)
		fmt.Fprintln(os.Stderr)
		subcommands.CmdHelp.CommandRun().Run(a, args, env)
		return 1
	}

	jd, err := decodeJobDefinition(ctx)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	authenticator, authClient, swarm, err := newSwarmClient(ctx, authOpts, jd.SwarmingServer)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	tok, err := authenticator.GetAccessToken(time.Minute)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "getting access token")
		return 1
	}
	info, err := googleoauth.GetTokenInfo(ctx, googleoauth.TokenInfoParams{
		AccessToken: tok.AccessToken,
	})
	uid := info.Email
	if uid == "" {
		uid = "uid:" + info.Sub
	}

	isoFlags, err := getIsolatedFlags(swarm)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}

	arc := mkArchiver(ctx, isoFlags, authClient)

	logging.Infof(ctx, "building swarming task")
	st, err := jd.GetSwarmingNewTask(ctx, uid, arc, jd.SwarmingServer)
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}
	logging.Infof(ctx, "building swarming task: done")

	if c.dump {
		err := json.NewEncoder(os.Stdout).Encode(st)
		if err != nil {
			logging.Errorf(ctx, "fatal error: %s", err)
			return 1
		}
		return 0
	}

	logging.Infof(ctx, "launching swarming task")
	req, err := swarm.Tasks.New(st).Do()
	if err != nil {
		logging.Errorf(ctx, "fatal error: %s", err)
		return 1
	}
	logging.Infof(ctx, "launching swarming task: done")

	logging.Infof(ctx, "Launched swarming task: %s/task?id=%s",
		jd.SwarmingServer, req.TaskId)
	return 0
}
