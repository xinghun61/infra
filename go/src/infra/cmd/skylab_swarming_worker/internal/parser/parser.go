// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package parser provides Go bindings for running autotest_status_parser.
package parser

import (
	"bytes"
	"fmt"
	"io"
	"os/exec"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/annotations"
)

const parseSubcommand = "parse"
const logdogStepName = "Test results"

// Args contains information needed to run the parser command.
type Args struct {
	ParserPath   string
	ResultsDir   string
	StainlessURL string
	Failed       bool
}

// GetResults calls autotest_status_parser and returns its stdout.
func GetResults(a Args, w io.Writer) ([]byte, error) {
	annotations.SeedStep(w, logdogStepName)
	annotations.StepCursor(w, logdogStepName)
	annotations.StepStarted(w)
	annotations.StepLink(w, "Full logs (Stainless)", a.StainlessURL)

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

	if a.Failed {
		annotations.StepFailure(w)
	}

	fmt.Fprintf(w, "Test results summary:\n%s", output)

	if err := annotateTestCases(output, a.Failed, w); err != nil {
		fmt.Fprintf(w,
			"Failed to create logdog annotations for test cases due to error %s",
			err.Error())
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

// annotateTestCases prints LogDog annotations for test cases in the output blob.
func annotateTestCases(b []byte, runFailed bool, w io.Writer) error {
	var r skylab_test_runner.Result
	if err := jsonpb.Unmarshal(bytes.NewReader(b), &r); err != nil {
		fmt.Printf("error: %s", err.Error())
		return err
	}
	fmt.Printf("%v", r)

	failureEncountered := false

	for _, s := range r.Prejob.GetStep() {
		failed := s.GetVerdict() != skylab_test_runner.Result_Prejob_Step_VERDICT_PASS

		if failed {
			failureEncountered = true
		}

		annotateTestCase(s.GetName(), failed, s.GetHumanReadableSummary(), w)
	}

	for _, tc := range r.GetAutotestResult().GetTestCases() {
		failed := tc.GetVerdict() != skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS

		if failed {
			failureEncountered = true
		}

		annotateTestCase(tc.GetName(), failed, tc.GetHumanReadableSummary(), w)
	}

	// If no individual test case can be blamed for the overall failure,
	// blame the test executor process.
	if runFailed && !failureEncountered {
		annotateTestCase("autoserv", true,
			"autoserv failed. The test list is likely incomplete. "+
				"Consult autoserv.ERROR for more details.", w)
	}

	return nil
}

func annotateTestCase(name string, failed bool, summary string, w io.Writer) {
	annotations.SeedStep(w, name)
	annotations.StepCursor(w, name)
	annotations.StepNestLevel(w, 1)
	annotations.StepStarted(w)

	if failed {
		annotations.StepFailure(w)
	}

	if summary != "" {
		fmt.Fprintf(w, summary)
	}

	annotations.StepClosed(w)
	annotations.StepCursor(w, logdogStepName)
}
