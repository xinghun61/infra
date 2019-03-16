// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command skmigration is a tool to help manage DUT inventory split between
// Autotest and Skylab during the migration.
//
// This tool is intended to be used only during the migration of DUTs from
// Autotest to Skylab. Once all DUTs are migrated, no directly manipulation of
// inventory data will be allowed.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/libs/skylab/inventory/cmd/skmigration/internal/cmd"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "skmigration",
		Title: "Tool to aid migration of DUTs from Autotest to Skylab",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			cmd.ImportServoAttributes,
			cmd.ListDuplicates,
			cmd.Migrate,
			cmd.Summarize,
		},
	}
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), nil))
}
