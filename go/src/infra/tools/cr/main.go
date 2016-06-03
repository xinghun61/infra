// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Core of the Chrome Infrastructure CLI SDK. Provides autoupdate, module
discovery, module installation, and help.
*/

package main

import (
	"flag"
	"fmt"
	"os"

	"infra/tools/cr/lib/subcommand"
	"infra/tools/cr/lib/terminal"

	_ "infra/tools/cr/cmd/firstrun"
)

var (
	// The subcommand which will be executed.
	cmd *subcommand.Subcommand

	// Accessible variables for global flags.
	help    bool
	verbose bool
)

func printSubcommands() {
	fmt.Println("Available subcommands are:")
	subcommand.Tabulate()
	fmt.Println("")
}

func printCrHelp() {
	fmt.Print(`The cr tool intelligently manages the Chrome Infra command-line SDK.

You must provide a subcommand. Run 'cr help' for a list of available commands.
`)
	printSubcommands()
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("No subcommand provided.")
		printCrHelp()
		os.Exit(-1)
	}

	cmd := subcommand.Get(os.Args[1])
	if cmd == nil {
		fmt.Printf("Unrecognized subcommand '%v'.\n", os.Args[1])
		printCrHelp()
		os.Exit(-1)
	}

	flags := flag.NewFlagSet("flags", flag.ExitOnError)
	flags.BoolVar(&help, "help", false, "print help for the given command")
	flags.BoolVar(&verbose, "verbose", false, "print more verbose output")
	cmd.InitFlags(flags)
	flags.Parse(os.Args[2:])

	if verbose {
		terminal.ShowDebug = true
	}

	// There are two ways to get help: 'cr help foo' and 'cr foo --help'. The
	// former is handled by setSubcommand, the latter is special-cased here.
	if help {
		cmd.Help(flags)
		return
	}

	err := cmd.Run(flags)
	if err != nil {
		fmt.Print(err)
	}
}
