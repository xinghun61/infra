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
		Name: "try-recipe",
		Title: `Launches recipes into the cloud.

Allows local modifications to tasks to be launched directly in swarming. This is
meant to aid in debugging and development for recipes on swarming.

This command is meant to be used multiple times in a pipeline. The flow is
generally:

  get | isolate? | edit? | launch

Where the isolate and edit steps are optional. The output of the commands on
stdout is a JobDefinition JSON document, and the input to the commands is this
same JobDefinition JSON document. At any stage in the pipeline, you may,
of course, hand-edit the JobDefinition.

Example:
  try-recipe get-builder bucket_name:builder_name | \
    try-recipe edit -env CHROME_HEADLESS=1 | \
    try-recipe isolate -O recipe_engine=/path/to/recipe_engine | \
    try-recipe launch

This would pull the recipe job from the named swarming task, set the
$CHROME_HEADLESS environment variable to 1, isolate the recipes from the
current working directory (overriding the recipe engine to the one indicated
by -O), and then launch the modified task on swarming.`,

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
			// TODO(iannucci): `get-milo` to scrape from milo
			// TODO(iannucci): `get-buildbot` to emulate/scrape from a buildbot
			getBuilderCmd(authDefaults),

			// commands to isolate recipes.
			isolateCmd(authDefaults),

			// commands to edit JobDescriptions.
			editCmd(),
			editSystemCmd(),

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
