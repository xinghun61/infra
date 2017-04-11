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
		Name:  "try-recipe",
		Title: "Launches recipes into the cloud.",

		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)

			ctx = (&log.Config{Level: log.Info}).Set(ctx)
			return handleInterruption(ctx)
		},

		Commands: []*subcommands.Command{
			isolateCmd(authDefaults),

			authcli.SubcommandLogin(authDefaults, "auth-login", false),
			authcli.SubcommandLogout(authDefaults, "auth-logout", false),
			authcli.SubcommandInfo(authDefaults, "auth-info", false),

			subcommands.CmdHelp,
			version.SubcommandVersion,
		},
	}

	os.Exit(subcommands.Run(&application, nil))
}
