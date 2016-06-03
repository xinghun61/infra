// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The 'cr help' command. It is implemented here, rather than in the cmd/
// package, because it needs to be able to reference the other subcommands.

package main

import (
	"flag"
	"fmt"

	"infra/tools/cr/lib/subcommand"
)

var shortHelp = "Print help for a subcommand."

var longHelp = `The help subcommand prints long-form help for the top-level cr command
and its subcommands. Run 'cr help' for a list of available commands.

Examples:
  cr help             # print top-level help and list of commands
  cr help firstrun    # print help for the 'firstrun' subcommand
  cr firstrun --help  # same as above`

func helpRun(flags *flag.FlagSet) error {
	if flags.NArg() == 0 {
		printCrHelp()
		return nil
	}
	if cmdForHelp := subcommand.Get(flags.Arg(0)); cmdForHelp != nil {
		cmdForHelp.InitFlags(flags)
		cmdForHelp.Help(flags)
		return nil
	} else {
		return fmt.Errorf("Unrecognized subcommand for help '%v'.\n", flags.Arg(0))
	}
}

var helpCmd = subcommand.New("help", shortHelp, longHelp, nil, helpRun)
