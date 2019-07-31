// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"os/exec"
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
		UsageLine: "edit-isolated [transform_program args...]",
		ShortDesc: "Allows arbitrary local edits to the isolated input.",
		LongDesc: `Downloads the task isolated (if any) into a temporary folder,
and then waits for your edits.

If you don't specify "transform_program", this will prompt with the location of
the temporary folder, and will wait for you to hit <enter>. You may manually
edit the contents of the folder however you like, and on <enter> the contents
will be isolated and deleted, and the new isolated will be attached to the task.

If "transform_program" and any arguments are specified, it will be run like:

   cd /path/to/isolated/dir && transform_program args...

And there will be no interactive prompt. All stdout/stderr from
transform_program will be redirected to stderr.
`,

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

	transformProgram []string

	logCfg    logging.Config
	authFlags authcli.Flags
}

func (c *cmdEditIsolated) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	c.transformProgram = args
	return c.authFlags.Options()
}

func (c *cmdEditIsolated) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	if runtime.GOOS == "windows" && len(c.transformProgram) == 0 {
		logging.Errorf(ctx, "led edit-isolated interactive mode is not currently implemented for windows.")
		logging.Errorf(ctx, "If you see this, please comment on crbug.com/912757.")
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
		if len(c.transformProgram) == 0 {
			logging.Infof(ctx, "")
			logging.Infof(ctx, "Edit files as you wish in:")
			logging.Infof(ctx, "\t%s", tdir)
			if err = prompt(ctx); err != nil {
				return err
			}
		} else {
			logging.Infof(ctx, "Invoking transform_program: %q", c.transformProgram)
			cmd := exec.CommandContext(ctx, c.transformProgram[0], c.transformProgram[1:]...)
			cmd.Stdout = os.Stderr
			cmd.Stderr = os.Stderr
			cmd.Dir = tdir
			if err := cmd.Run(); err != nil {
				return errors.Annotate(err, "running transform_program").Err()
			}
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
