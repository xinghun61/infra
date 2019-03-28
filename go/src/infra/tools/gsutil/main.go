// Copyright 2019 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"os"
	"os/signal"

	"cloud.google.com/go/storage"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/client/versioncli"
	"go.chromium.org/luci/common/cli"
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
	authDefaults := chromeinfra.DefaultAuthOptions()
	// Right now we only have 'cat' so only request read-only.
	authDefaults.Scopes = append(authDefaults.Scopes, storage.ScopeReadOnly)

	var application = cli.Application{
		Name: "gsutil",
		Title: `A golang gsutil replacement that undestands LUCI authentication.

The source for gsutil lives at:
  https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tools/gsutil
`,
		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)

			ctx = (&log.Config{Level: log.Info}).Set(ctx)
			return handleInterruption(ctx)
		},

		Commands: []*subcommands.Command{
			catCmd(authDefaults),

			{}, // spacer

			subcommands.CmdHelp,
			versioncli.CmdVersion("gsutil"),

			{}, // spacer

			authcli.SubcommandLogin(authDefaults, "auth-login", false),
			authcli.SubcommandLogout(authDefaults, "auth-logout", false),
			authcli.SubcommandInfo(authDefaults, "auth-info", false),
		},
	}

	os.Exit(subcommands.Run(&application, nil))
}
