// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command qscheduler is the tool to interact with quotascheduler.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/qscheduler/internal/cmd"
	"infra/cmd/qscheduler/internal/site"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "quotascheduler",
		Title: "Universal tool for interacting with quotascheduler",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			subcommands.Section("Auth"),
			authcli.SubcommandInfo(site.DefaultAuthOptions, "whoami", false),
			authcli.SubcommandLogin(site.DefaultAuthOptions, "login", false),
			authcli.SubcommandLogout(site.DefaultAuthOptions, "logout", false),

			subcommands.Section("Administration"),
			cmd.Create,
			cmd.AddAccount,

			subcommands.Section("View"),
			cmd.Inspect,
		},
	}
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), nil))
}
