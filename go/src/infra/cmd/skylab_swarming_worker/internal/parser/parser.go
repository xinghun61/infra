// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package parser provides Go bindings for running autotest_status_parser.
package parser

import (
	"fmt"
	"io"
	"os/exec"
	"strings"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/annotations"
)

const parseSubcommand = "parse"

// Args contains information needed to run the parser command.
type Args struct {
	ParserPath string
	ResultsDir string
}

// GetResults calls autotest_status_parser and returns its stdout.
func GetResults(a Args, w io.Writer) ([]byte, error) {
	annotations.SeedStep(w, "Get results")
	annotations.StepCursor(w, "Get results")
	annotations.StepStarted(w)
	defer annotations.StepClosed(w)

	cmd, err := parseCommand(a)
	if err != nil {
		annotations.StepException(w)
		return nil, errors.Annotate(err, "parse autotest status").Err()
	}
	fmt.Fprintf(w, "Running %s %s", cmd.Path, strings.Join(cmd.Args, " "))
	cmd.Stderr = w

	output, err := cmd.Output()
	if err != nil {
		annotations.StepException(w)
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
