// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command cros-admin is the Chrome OS infrastructure admin tool.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/skylab/internal/cmd"
	"infra/cmd/skylab/internal/site"
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
			cmd.Update,
			cmd.Version,
			subcommands.Section("Authentication"),
			authcli.SubcommandLogin(site.DefaultAuthOptions, "login", false),
			authcli.SubcommandLogout(site.DefaultAuthOptions, "logout", false),
			authcli.SubcommandInfo(site.DefaultAuthOptions, "whoami", false),
			subcommands.Section("Inventory Queries"),
			cmd.Diagnose,
			cmd.DutInfo,
			cmd.DutList,
			cmd.Inventory,
			cmd.ListRemovedDuts,
			subcommands.Section("Inventory Operations"),
			cmd.AddDut,
			cmd.QuickAddDuts,
			cmd.AssignDuts,
			cmd.RemoveDuts,
			cmd.UpdateDut,
			subcommands.Section("Pool Operations"),
			cmd.EnsurePoolHealthy,
			cmd.ResizePool,
			subcommands.Section("Tasks"),
			cmd.BackfillRequest,
			cmd.CreateTest,
			cmd.CreateSuite,
			cmd.CreateTestPlan,
			cmd.LeaseDut,
			cmd.ReleaseDuts,
			cmd.Repair,
			cmd.RerunTasks,
			subcommands.Section("Drone Queen Inspection"),
			cmd.QueenInspectDuts,
			cmd.QueenInspectDrones,
			cmd.QueenPushDuts,
			subcommands.Section("Internal use"),
			cmd.InternalListDroneDuts,
			cmd.InternalPrintBotInfo,
			cmd.InternalVerifyInventory,
			cmd.WaitTask,
			cmd.WaitTasks,
		},
	}
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), nil))
}
