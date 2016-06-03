// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

// unix-specific function implementations for the firstrun subcommand.

package firstrun

import (
	"errors"
)

var executableName = "cr"

// firstrunPromptInstallDir prompts the user for a directory path to install cr.
func firstrunPromptInstallDir() (string, error) {
	return "", errors.New("firstrun_unix.firstrunPromptInstallDir not yet implemented")
	// TODO(agable): Figure out a sane place to suggest.
	// TODO(agable): Suggest it and ask the user for an alternative.
	// TODO(agable): Check that the chosen directory makes sense.
}

// firstrunInitInstallDir sets up the selected directory to house cr. It creates
// the modules/ and bin/ subdirectories, places the cr executable in the
// top level, and symlinks it into bin/.
func firstrunInitInstallDir(dir string) error {
	return errors.New("firstrun_unix.firstrunInitInstallDir not yet implemented")
	// TODO(agable): Create the cr/ directory.
	// TODO(agable): Copy this executable into the cr/ directory.
	// TODO(agable): Create the bin/ subdirectory.
	// TODO(agable): Add a symlink to the cr executable in the bin/ subdirectory.
	// TODO(agable): Create the modules/ subdirectory.
}

// firstrunUpdatePath finds the rcfile in which $PATH is set, sees if it can
// automatically update it, and prompts the user for permission to do so.
func firstrunUpdatePath(dir string) error {
	return errors.New("firstrun_unix.firstrunUpdatePath not yet implemented")
	// TODO(agable): Detect the user's default shell.
	// TODO(agable): Find their shell's rcfile.
	// TODO(agable): Find lines modifying $PATH in that file.
	// TODO(agable): Fine a line mentioning depot_tools.
	// TODO(agable): Produce a git-style diff adding the install bin/ dir after than line.
	// TODO(agable): Prompt the user to see if they want to apply that diff.
	// TODO(agable): Apply the diff, or print instructions on how to do it manually.
}

// firstrunPrintUpdatePathInstructions prints instructions for the user to
// update their $PATH manually. This is used if updatePath fails, or if the user
// declines to have their rcfile updated automatically.
func firstrunPrintUpdatePathInstructions() error {
	return errors.New("firstrun_unix.firstrunPrintUpdatePathInstructions not yet implemented")
}
