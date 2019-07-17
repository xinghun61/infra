// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package cmd

import (
	"strconv"
	"strings"

	"golang.org/x/sys/unix"
)

// exitedWithErrors parses the exit status file and returns true iff the server
// job exited with errors.
func exitedWithErrors(content string) bool {
	lines := strings.Split(content, "\n")
	if len(lines) < 2 {
		// Couldn't find the status code.
		return true
	}

	statusCode, err := strconv.Atoi(lines[1])
	if err != nil {
		// Couldn't parse the status code.
		return true
	}

	status := unix.WaitStatus(statusCode)
	if !status.Exited() {
		// Server job was aborted by a signal.
		return true
	}
	if status.ExitStatus() != 0 {
		// Server job process completed with an error.
		return true
	}
	return false
}
