// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"
	"os/signal"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"github.com/luci/luci-go/cipd/version"
	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/data/rand/mathrand"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/hardcoded/chromeinfra"
)

func handleInterruption(ctx context.Context) context.Context {
	ctx, cancel := context.WithCancel(ctx)
	signalC := make(chan os.Signal)
	signal.Notify(signalC, os.Interrupt)
	go func() {
		interrupted := false
		for range signalC {
			if interrupted {
				os.Exit(1)
			}
			interrupted = true
			cancel()
		}
	}()
	return ctx
}

func main() {
	mathrand.SeedRandomly()

	authDefaults := chromeinfra.DefaultAuthOptions()

	var application = cli.Application{
		Name: "led",
		Title: `'LUCI editor' - Multi-service LUCI job debugging tool.

Allows local modifications to LUCI jobs to be launched directly in swarming.
This is meant to aid in debugging and development for the interaction of
multiple LUCI services:
  * buildbucket
  * swarming
  * isolate
  * recipes
  * logdog
  * milo

This command is meant to be used multiple times in a pipeline. The flow is
generally:

  get | edit* | launch

Where the edit step(s) are optional. The output of the commands on stdout is
a JobDefinition JSON document, and the input to the commands is this same
JobDefinition JSON document. At any stage in the pipeline, you may, of course,
hand-edit the JobDefinition.

Example:
  led get-builder bucket_name:builder_name | \
    led edit-recipe-bundle -O recipe_engine=/local/recipe_engine > job.json
  # edit job.json by hand to inspect
  led edit -env CHROME_HEADLESS=1 < job.json | \
    led launch

This would pull the recipe job from the named swarming task, then isolate the
recipes from the current working directory (with an override for the
recipe_engine), and inject the isolate hash into the job, saving the result to
job.json. The user thens inspects job.json to look at the full set of flags and
features. After inspecting/editing the job, the user pipes it back through the
edit subcommand to set the swarming envvar $CHROME_HEADLESS=1, and then launches
the edited task back to swarming.

The source for led lives at:
  https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tools/led

The spec (as it is) for JobDefinition is at:
  https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tools/led/job_def.go
`,

		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)

			ctx = (&log.Config{Level: log.Info}).Set(ctx)
			return handleInterruption(ctx)
		},

		Commands: []*subcommands.Command{
			// commands to obtain JobDescriptions. These all begin with `get`.
			// TODO(iannucci): `get` to scrape from any URL
			getSwarmCmd(authDefaults),
			// TODO(iannucci): `get-buildbot` to emulate/scrape from a buildbot
			getBuildCmd(authDefaults),
			getBuilderCmd(authDefaults),

			// commands to edit JobDescriptions.
			editCmd(),
			editSystemCmd(),
			editRecipeBundleCmd(authDefaults),
			editCrCLCmd(authDefaults),

			// commands to launch swarming tasks.
			launchCmd(authDefaults),
			// TODO(iannucci): launch-local to launch locally
			// TODO(iannucci): launch-buildbucket to launch on buildbucket

			{}, // spacer

			subcommands.CmdHelp,
			version.SubcommandVersion,

			{}, // spacer

			authcli.SubcommandLogin(authDefaults, "auth-login", false),
			authcli.SubcommandLogout(authDefaults, "auth-logout", false),
			authcli.SubcommandInfo(authDefaults, "auth-info", false),
		},
	}

	os.Exit(subcommands.Run(&application, nil))
}
