// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command cros-admin is the Chrome OS infrastructure admin tool.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/skylab/internal/cmd"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "skylab",
		Title: "Universal tool for Chrome OS Infra Skylab",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			// Main commands.
			cmd.BalancePool,
		},
	}
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), nil))
}
