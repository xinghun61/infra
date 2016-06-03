// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package firstrun contains the logic for the 'cr firstrun' command.
// Generally only executed once on a given machine, the firstrun command
// installs the cr tool, prepares a space for it to install modules, and
// adds it to $PATH.
package firstrun

import (
	"flag"
	"fmt"
	"strings"

	"infra/tools/cr/lib/subcommand"
	"infra/tools/cr/lib/terminal"
)

var (
	// Package-level variables for subcommand flags.
	path string
)

var shortHelp = "Install the cr tool and intelligently add it to $PATH."

var longHelp = `Given a path to a desired install directory, it takes ownership of that
directory, sets it up to support installation of modules, and adds the
directory to $PATH (by prompting to modify e.g. the registry or .bashrc).

The firstrun command is intended to only be run once, when first
installing the cr tool.

Examples:
  cr firstrun -verbose -path ~/local/bin/`

func flags(flags *flag.FlagSet) {
	flags.StringVar(&path, "path", "", "the path to install 'cr' in")
}

func run(flags *flag.FlagSet) error {
	preinstall, err := firstrunCheckNotInstalled()
	if err != nil {
		terminal.Print("Had difficulty determining if cr is already installed. Continuing.")
	}
	if preinstall != "" {
		prompt := fmt.Sprintf("It appears that cr is already installed at %v. Would you like to continue anyway? [y|N]", preinstall)
		ans, err := terminal.Prompt(prompt)
		if err != nil {
			return fmt.Errorf("Failed to get user input.")
		}
		if !strings.HasPrefix(strings.ToLower(ans), "y") {
			fmt.Printf("Aborting.")
			return nil
		}
	}
	// TODO(agable): Complement path flag with firstrunPromptInstallDir()
	return firstrunInitInstallDir(path)
}

// FirstrunCmd is a subcommand.Command representing the 'cr firstrun' command.
var FirstrunCmd = subcommand.New("firstrun", shortHelp, longHelp, flags, run)
