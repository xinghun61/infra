// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"runtime"
	"sync"
	"time"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/client/downloader"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/logging"
)

func editIsolated(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit-isolated",
		ShortDesc: "Allows arbitrary local edits to the isolated input.",
		LongDesc: `Downloads the task isolated (if any) into a temporary folder,
and then waits for your edits. When you're done editing the files in the folder,
hit <enter> and the folder contents will be isolated and deleted, and the new
isolated will be attached to the task.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEditIsolated{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			return ret
		},
	}
}

type cmdEditIsolated struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags
}

func (c *cmdEditIsolated) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %q", args).Err()
		return
	}

	return c.authFlags.Options()
}

func (c *cmdEditIsolated) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	if runtime.GOOS == "windows" {
		logging.Errorf(ctx, "led edit-isolated is not currently implemented for windows.")
		logging.Errorf(ctx, "If you see this, please comment on crbug.com/912757.")
		return 1
	}

	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	logging.Infof(ctx, "editing isolated")

	tdir, err := ioutil.TempDir("", "led-edit-isolated")
	if err != nil {
		logging.Errorf(ctx, "failed to create tempdir: %s", err)
		return 1
	}
	defer func() {
		if err = os.RemoveAll(tdir); err != nil {
			logging.Errorf(ctx, "failed to cleanup temp dir %q: %s", tdir, err)
		}
	}()

	err = editMode(ctx, func(jd *JobDefinition) error {
		authClient, swarm, err := newSwarmClient(ctx, authOpts, jd.SwarmingHostname)
		if err != nil {
			return err
		}

		isoFlags, err := getIsolatedFlags(swarm)
		if err != nil {
			return err
		}

		isoClient, err := newIsolatedClient(ctx, isoFlags, authClient)
		if err != nil {
			return err
		}

		currentIsolated := jd.Slices[0].U.RecipeIsolatedHash
		if currentIsolated == "" {
			if ir := jd.Slices[0].S.TaskSlice.Properties.InputsRef; ir != nil {
				currentIsolated = ir.Isolated
			}
		}
		var cmd []string
		var cwd string
		if currentIsolated != "" {
			var statMu sync.Mutex
			var previousStats *downloader.FileStats
			dl := downloader.New(ctx, isoClient, isolated.HexDigest(currentIsolated), tdir, &downloader.Options{
				FileStatsCallback: func(s downloader.FileStats, span time.Duration) {
					logging.Infof(ctx, "%s", s.StatLine(previousStats, span))
					statMu.Lock()
					previousStats = &s
					statMu.Unlock()
				},
			})

			if err = dl.Wait(); err != nil {
				return err
			}

			cmd, cwd, err = dl.CmdAndCwd()
			if err != nil {
				return err
			}
		}
		logging.Infof(ctx, "")
		logging.Infof(ctx, "Edit files as you wish in:")
		logging.Infof(ctx, "\t%s", tdir)
		if err = prompt(ctx); err != nil {
			return err
		}

		logging.Infof(ctx, "uploading new isolated")

		hash, err := isolateDirectory(ctx, isoClient, tdir)
		if err != nil {
			return err
		}
		logging.Infof(ctx, "isolated upload: done")

		ejd := jd.Edit()
		ejd.EditIsolated(string(hash), cmd, cwd)
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
