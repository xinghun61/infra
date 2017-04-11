// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"os"
	"path/filepath"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	"github.com/luci/luci-go/common/isolatedclient"
	"github.com/luci/luci-go/common/logging"
)

const defaultIsolateServer = "https://isolateserver.appspot.com"

func isolateCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "isolate [-O project_id=/path/to/local/repo]* [-I isolate_server]",
		ShortDesc: "Isolates a bundle of recipes from the current working directory.",
		LongDesc: `Takes recipes from the current repo (based on cwd), along with
		any supplied overrides, and pushes them to the isolate service.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdIsolate{}

			ret.authFlags.Register(&ret.Flags, authOpts)
			ret.isolateFlags.Init(&ret.Flags)

			ret.Flags.Var(&ret.overrides, "O",
				"override a repo dependency. Must be in the form of project_id=/path/to/local/repo. May be specified multiple times.")
			return ret
		},
	}
}

type cmdIsolate struct {
	subcommands.CommandRunBase

	authFlags    authcli.Flags
	isolateFlags isolatedclient.Flags

	overrides stringmapflag.Value
}

func (c *cmdIsolate) validateFlags(ctx context.Context) error {
	for k, v := range c.overrides {
		if k == "" {
			return errors.New("override has empty project_id")
		}
		if v == "" {
			return errors.Reason("override %(key)q has empty repo path").D("key", k).Err()
		}
		v, err := filepath.Abs(v)
		if err != nil {
			return errors.Annotate(err).Reason("override %(key)q").D("key", k).Err()
		}
		c.overrides[k] = v

		switch fi, err := os.Stat(v); {
		case err != nil:
			return errors.Annotate(err).Reason("override %(key)q").D("key", k).Err()
		case !fi.IsDir():
			return errors.Reason("override %(key)q: not a directory").D("key", k).Err()
		}
	}

	if c.isolateFlags.ServerURL == "" {
		c.isolateFlags.ServerURL = defaultIsolateServer
	}
	if err := c.isolateFlags.Parse(); err != nil {
		return errors.Annotate(err).Reason("bad isolate flags").Err()
	}

	return nil
}

func (c *cmdIsolate) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if err := c.validateFlags(ctx); err != nil {
		logging.Errorf(ctx, "bad arguments: %s", err)
		fmt.Fprintln(os.Stderr)
		subcommands.CmdHelp.CommandRun().Run(a, args, env)
		return 1
	}

	panic("not implemented")
}
