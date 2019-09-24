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

	"infra/cros/cmd/phosphorus/internal/cmd"
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "phosphorus",
		Title: "A tool for running Autotest tests and uploading their results.",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,

			cmd.Prejob,
			cmd.RunTest,
			cmd.UploadToTKO,
		},
	}
}

func main() {
	os.Exit(subcommands.Run(getApplication(), nil))
}
