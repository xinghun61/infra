// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package parser provides Go bindings for running autotest_status_parser.
package parser

import (
	"os/exec"

	"go.chromium.org/luci/common/errors"
)

const parseSubcommand = "parse"

// Args contains information needed to run the parser command.
type Args struct {
	ParserPath string
	ResultsDir string
}

// GetResults calls autotest_status_parser and returns its stdout.
func GetResults(a Args) ([]byte, error) {
	cmd, err := parseCommand(a)
	if err != nil {
		return nil, errors.Annotate(err, "parse autotest status").Err()
	}
	output, err := cmd.Output()
	if err != nil {
		return nil, errors.Annotate(err, "parse autotest status").Err()
	}
	return output, nil
}

// parseCommand creates an exec.Cmd for running the results parser.
func parseCommand(a Args) (*exec.Cmd, error) {
	if a.ParserPath == "" {
		return nil, errors.Reason("No autotest_status_parser binary specified").Err()
	}
	if a.ResultsDir == "" {
		return nil, errors.Reason("No results directory provided for parsing").Err()
	}

	return exec.Command(a.ParserPath, parseSubcommand, a.ResultsDir), nil
}
