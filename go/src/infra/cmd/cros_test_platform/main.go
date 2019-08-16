// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command cros_test_platform implements the cros_test_platform recipe's steps.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/cros_test_platform/internal/cmd"
	"infra/cmd/cros_test_platform/internal/site"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "cros_test_platform",
		Title: "Binary steps implementations for cros_test_platform recipe.",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			subcommands.Section("Authentication"),
			authcli.SubcommandLogin(site.DefaultAuthOptions, "login", false),
			authcli.SubcommandLogout(site.DefaultAuthOptions, "logout", false),
			authcli.SubcommandInfo(site.DefaultAuthOptions, "whoami", false),

			subcommands.Section("Steps"),
			// The cros_test_platform recipe runs subcommands in this order:
			cmd.Enumerate,
			cmd.SchedulerTrafficSplit,
			// The cros_test_platform recipe concludes with one of these
			// two subcommands:
			cmd.AutotestExecute,
			cmd.SkylabExecute,
		},
		EnvVars: map[string]subcommands.EnvVarDefinition{
			"SWARMING_TASK_ID": {
				ShortDesc: "Swarming task id in which this task is running.",
			},
			"SWARMING_SERVER": {
				ShortDesc: "Swarming server that this task belongs to.",
			},
		},
	}
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), nil))
}
