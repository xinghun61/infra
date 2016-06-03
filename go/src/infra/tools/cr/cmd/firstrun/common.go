// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// OS-agnostic helper functions which are called from run().

package firstrun

import (
	"errors"
	"os"
	"path/filepath"

	"infra/tools/cr/lib/terminal"
)

var getenv = os.Getenv
var stat = os.Stat

// firstrunCheckNotInstalled is a sanity check to make sure that the user really
// wants to do firstrun again, if it looks like cr is already installed.
func firstrunCheckNotInstalled() (string, error) {
	terminal.Debug("Checking to make sure cr isn't already installed...")
	// Look for paths on $PATH that end in /cr/bin.
	pathenv := getenv("PATH")
	if pathenv == "" {
		return "", errors.New("no $PATH variable found in the environment")
	}
	var possibleDirs []string
	for _, elem := range filepath.SplitList(pathenv) {
		head, bindir := filepath.Split(elem)
		crdir := filepath.Base(head)
		if crdir == "cr" && bindir == "bin" {
			possibleDirs = append(possibleDirs, elem)
		}
	}
	// Check to see if an executable called 'cr' is in those paths.
	var statErr error
	for _, dir := range possibleDirs {
		info, err := stat(filepath.Join(dir, executableName))
		if os.IsNotExist(err) {
			continue
		} else if err != nil {
			statErr = err
			continue
		}
		if info.Mode()&0111 != 0 {
			return filepath.Join(dir, executableName), nil
		}
	}
	// We didn't find an executable; if we ran into an error, return that.
	return "", statErr
}
