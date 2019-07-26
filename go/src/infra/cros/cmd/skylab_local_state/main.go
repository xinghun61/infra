// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command autotest_status_parser extracts individual test case results from status.log.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cros/cmd/skylab_local_state/internal/cmd"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "skylab_local_state",
		Title: "A tool for interacting with the local state files.",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			cmd.Load,
			cmd.Save,
		},
	}
}

func main() {
	os.Exit(subcommands.Run(getApplication(), nil))
}
