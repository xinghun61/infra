// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/cros/ipcpubsub/internal/cmd"
	"infra/cmd/cros/ipcpubsub/internal/site"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "ipcpubsub",
		Title: "Tool for inter-process communication via pubsub",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			subcommands.Section("Auth"),
			authcli.SubcommandInfo(site.DefaultAuthOptions, "whoami", false),
			authcli.SubcommandLogin(site.DefaultAuthOptions, "login", false),
			authcli.SubcommandLogout(site.DefaultAuthOptions, "logout", false),

			subcommands.Section("Pub/Sub"),
			cmd.CmdPublish,
			cmd.CmdSubscribe,
		},
	}
}

func main() {
	os.Exit(subcommands.Run(getApplication(), nil))
}
