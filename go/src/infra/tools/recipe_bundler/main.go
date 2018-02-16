// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"
	"os/signal"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/cipd/version"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/hardcoded/chromeinfra"
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
		Name: "recipe_bundler",
		Title: `"Recipe Bundler"

This tool is used to bundle [recipes] and upload them to [CIPD]. This is used
in conjunction with the infra.git "recipe_bundler" recipe.

[recipes]: https://chromium.googlesource.com/infra/luci/recipes-py
[CIPD]: https://chromium.googlesource.com/infra/luci/luci-go/+/master/cipd/
		`,

		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)

			ctx = (&log.Config{Level: log.Info}).Set(ctx)
			return handleInterruption(ctx)
		},

		Commands: []*subcommands.Command{
			bundleCmd(authDefaults),

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
