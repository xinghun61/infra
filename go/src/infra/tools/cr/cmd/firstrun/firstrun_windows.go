// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Windows-specific function implementations for the firstrun subcommand.

package firstrun

import (
	"errors"
)

var executableName = "cr.exe"

// firstrunPromptInstallDir prompts the user for a directory path to install.
func firstrunPromptInstallDir() (string, error) {
	return "", errors.New("firstrun_windows.firstrunPromptInstallDir not yet implemented")
}

// firstrunInitInstallDir sets up the selected directory to house cr. It creates
// the modules/ and bin/ subdirectories, places cr.exe in the top level, and
// symlinks it into bin/.
func firstrunInitInstallDir(dir string) error {
	return errors.New("firstrun_windows.firstrunInitInstallDir not yet implemented")
}

// firstrunUpdatePath finds the registry entry for %PATH%, sees if it can
// automatically update it, and prompts the user for permission to do so.
func firstrunUpdatePath(dir string) error {
	return errors.New("firstrun_windows.firstrunUpdatePath not yet implemented")
}

// firstrunPrintUpdatePathInstructions prints instructions for the user to
// update their %PATH% manually. This is used if updatePath fails, or if the
// user declines to have their registry updated automatically.
func firstrunPrintUpdatePathInstructions() error {
	return errors.New("firstrun_windows.firstrunPrintUpdatePathInstructions not yet implemented")
}
