// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"path/filepath"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
)

const (
	testSubdir         = "autoserv_test"
	resultsSummaryFile = "status.log"
	exitStatusFile     = ".autoserv_execute"

	verdictStringPrefix = "END "
	undefinedName       = "----"
)

var prejobPrefixes = []string{"provision", "prejob"}

// Parse subcommand: Extract test case results from status.log.
var Parse = &subcommands.Command{
	UsageLine: "parse DIR",
	ShortDesc: "Extract test case results from an autotest results directory.",
	LongDesc: `Extract test case results from an autotest results directory.

Parse the test result summary file (status.log) and the exit code file
(.autoserv_execute) created by the autotest harness inside DIR. The parsing is
a simplified version of the one done by tko/parse.

Write the parsed test case results as a JSON-pb
test_platform/skylab_test_runner/result.proto to stdout.`,
	CommandRun: func() subcommands.CommandRun {
		c := &parseRun{}
		return c
	},
}

type parseRun struct {
	subcommands.CommandRunBase
}

func (c *parseRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *parseRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
	}
	dir := c.Flags.Args()[0]

	testDir := filepath.Join(dir, testSubdir)
	autotestResult := getTestResults(testDir)

	prejobResult := getPrejobResults(dir)

	result := skylab_test_runner.Result{
		Harness: &skylab_test_runner.Result_AutotestResult{
			AutotestResult: &autotestResult,
		},
		Prejob: &prejobResult,
	}

	return printProtoJSON(a.GetOut(), &result)
}

func (c *parseRun) validateArgs() error {
	if c.Flags.NArg() != 1 {
		return errors.New("must specify exactly 1 results directory to parse")
	}
	return nil
}

// getTestResults extracts all test case results from the status.log file
// inside the given results directory.
func getTestResults(dir string) skylab_test_runner.Result_Autotest {
	resultsSummaryPath := filepath.Join(dir, resultsSummaryFile)
	resultsSummaryContent, err := ioutil.ReadFile(resultsSummaryPath)

	if err != nil {
		// Errors in reading status.log are expected when the server
		// job is aborted.
		return skylab_test_runner.Result_Autotest{
			Incomplete: true,
		}
	}

	testCases := parseResultsFile(string(resultsSummaryContent))

	exitStatusFilePath := filepath.Join(dir, exitStatusFile)
	exitStatusContent, err := ioutil.ReadFile(exitStatusFilePath)

	if err != nil {
		return skylab_test_runner.Result_Autotest{
			TestCases:  testCases,
			Incomplete: true,
		}
	}

	incomplete := exitedWithErrors(string(exitStatusContent))

	return skylab_test_runner.Result_Autotest{
		TestCases:  testCases,
		Incomplete: incomplete,
	}
}

type prejobInfo struct {
	Name string
	Dir  string
}

func getPrejobResults(dir string) skylab_test_runner.Result_Prejob {
	var steps []*skylab_test_runner.Result_Prejob_Step

	prejobs, err := getPrejobs(dir)

	if err != nil {
		// TODO(zamorzaev): find a better way to surface this error.
		return skylab_test_runner.Result_Prejob{
			Step: []*skylab_test_runner.Result_Prejob_Step{
				{
					Name:    "unknown",
					Verdict: skylab_test_runner.Result_Prejob_Step_VERDICT_FAIL,
				},
			},
		}
	}

	for _, prejob := range prejobs {
		steps = append(steps, &skylab_test_runner.Result_Prejob_Step{
			Name:    prejob.Name,
			Verdict: getPrejobVerdict(prejob.Dir),
		})
	}
	return skylab_test_runner.Result_Prejob{
		Step: steps,
	}
}

func getPrejobs(parentDir string) ([]prejobInfo, error) {
	prejobs := []prejobInfo{}
	for _, prefix := range prejobPrefixes {
		fullPrefix := filepath.Join(parentDir, prefix)
		regex := fullPrefix + "*"
		prejobDirList, err := filepath.Glob(regex)
		if err != nil {
			return nil, fmt.Errorf("bad regex: %s", regex)
		}
		if len(prejobDirList) > 1 {
			return nil, errors.New("more than one directory for the same prejob type")
		}
		if len(prejobDirList) == 1 {
			prejobs = append(prejobs, prejobInfo{
				Name: prefix,
				Dir:  prejobDirList[0],
			})
		}
	}
	return prejobs, nil
}

func getPrejobVerdict(prejobDir string) skylab_test_runner.Result_Prejob_Step_Verdict {
	exitStatusFilePath := filepath.Join(prejobDir, exitStatusFile)
	exitStatusContent, err := ioutil.ReadFile(exitStatusFilePath)

	if err != nil {
		return skylab_test_runner.Result_Prejob_Step_VERDICT_FAIL
	}

	if exitedWithErrors(string(exitStatusContent)) {
		return skylab_test_runner.Result_Prejob_Step_VERDICT_FAIL
	}

	return skylab_test_runner.Result_Prejob_Step_VERDICT_PASS
}

// parseResultsFile extracts all test case results from contents of a
// status.log file.
func parseResultsFile(contents string) []*skylab_test_runner.Result_Autotest_TestCase {
	lines := strings.Split(contents, "\n")
	testCases := []*skylab_test_runner.Result_Autotest_TestCase{}

	for _, line := range lines {
		testCase := parseLine(line)
		if testCase != nil {
			testCases = append(testCases, testCase)
		}
	}
	// Stay consistent with the default value which is nil.
	if len(testCases) == 0 {
		return nil
	}
	return testCases
}

// parseLine decides whether a given line of status.log contains a test case
// verdict and if so converts it into a TestCase proto.
func parseLine(line string) *skylab_test_runner.Result_Autotest_TestCase {
	parts := strings.Split(strings.Trim(line, "\t"), "\t")
	if !strings.HasPrefix(parts[0], verdictStringPrefix) {
		return nil
	}
	if len(parts) < 3 {
		return nil
	}

	testCaseName := parts[2] // Declared test name if any.
	if testCaseName == undefinedName {
		// Use subdir name if declared name not available.
		testCaseName = parts[1]
	}
	if testCaseName == undefinedName || testCaseName == "reboot" {
		// Ignore unnamed and reboot test case substeps.
		return nil
	}

	verdict := parseVerdict(parts[0])
	testCase := skylab_test_runner.Result_Autotest_TestCase{
		Name:    testCaseName,
		Verdict: verdict,
	}
	return &testCase
}

// parseVerdict converts a verdict string from status.log (e.g. "END GOOD",
// "END FAIL" etc) into a Verdict proto.
func parseVerdict(verdict string) skylab_test_runner.Result_Autotest_TestCase_Verdict {
	// Remove "END " prefix.
	switch verdict[len(verdictStringPrefix):] {
	case "GOOD", "WARN":
		return skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS
	}
	return skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL
}

// printProtoJSON prints the parsed test cases as a JSON-pb to stdout.
func printProtoJSON(w io.Writer, result *skylab_test_runner.Result) error {
	m := jsonpb.Marshaler{
		EnumsAsInts: false,
		Indent:      "\t",
	}
	return m.Marshal(w, result)
}
