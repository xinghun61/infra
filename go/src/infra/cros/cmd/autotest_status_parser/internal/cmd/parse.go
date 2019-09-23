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
	var stack testCaseStack
	lines := strings.Split(contents, "\n")
	testCases := []*skylab_test_runner.Result_Autotest_TestCase{}

	for _, line := range lines {
		stack.ParseLine(line)

		testCase := stack.PopFullyParsedTestCase()

		if testCase == nil {
			continue
		}

		if isLegalTestCaseName(testCase.Name) {
			testCases = append(testCases, testCase)
		}
	}

	testCases = append(testCases, stack.Flush()...)

	// Stay consistent with the default value which is nil.
	if len(testCases) == 0 {
		return nil
	}
	return testCases
}

type testCaseStack struct {
	testCases []skylab_test_runner.Result_Autotest_TestCase
}

// ParseLine parses a line from status.log in the context of the current test
// case stack.
func (s *testCaseStack) ParseLine(line string) {
	parts := strings.Split(strings.TrimLeft(line, "\t"), "\t")
	if len(parts) < 3 {
		return
	}

	switch {
	case isStartingEvent(parts[0]):
		testCaseName := parts[2] // Declared test name if any.
		if testCaseName == undefinedName {
			// Use subdir name if declared name not available.
			testCaseName = parts[1]
		}
		s.push(testCaseName)

	case isFinalEvent(parts[0]):
		s.setVerdict(parseVerdict(parts[0]))

	case isStatusUpdateEvent(parts[0]):
		s.addSummary(parts[len(parts)-1])
	}
}

// PopFullyParsedTestCase pops and returns the top test case of the stack, if
// it is fully parsed. If the top of the stack is only partially parsed, this
// function returns nil.
func (s *testCaseStack) PopFullyParsedTestCase() *skylab_test_runner.Result_Autotest_TestCase {
	if len(s.testCases) == 0 {
		return nil
	}

	r := s.testCases[len(s.testCases)-1]

	// The test case is not fully parsed.
	if r.Verdict == skylab_test_runner.Result_Autotest_TestCase_VERDICT_UNDEFINED {
		return nil
	}

	s.testCases = s.testCases[:len(s.testCases)-1]
	return &r
}

// Flush pops all test cases currently in the stack, declares them failed and
// returns them.
func (s *testCaseStack) Flush() []*skylab_test_runner.Result_Autotest_TestCase {
	r := []*skylab_test_runner.Result_Autotest_TestCase{}

	for {
		s.setVerdict(skylab_test_runner.Result_Autotest_TestCase_VERDICT_FAIL)

		tc := s.PopFullyParsedTestCase()

		if tc == nil {
			break
		}

		r = append(r, tc)
	}

	return r
}

// push adds a test case with a given name to the stack.
func (s *testCaseStack) push(name string) {
	if s == nil {
		panic("the test case stack is nil")
	}

	tc := skylab_test_runner.Result_Autotest_TestCase{
		Name: name,
	}
	s.testCases = append(s.testCases, tc)
}

// addSummary appends a string to the human_readable_summary of the top
// test case in the stack.
func (s *testCaseStack) addSummary(summary string) {
	// Ignore comments that do not correspond to a specific test case.
	if len(s.testCases) == 0 {
		return
	}
	if summary == "" {
		return
	}

	s.testCases[len(s.testCases)-1].HumanReadableSummary += summary + "\n"
}

// setVerdict sets the verdict of the top test case in the stack.
func (s *testCaseStack) setVerdict(verdict skylab_test_runner.Result_Autotest_TestCase_Verdict) {
	if len(s.testCases) == 0 {
		return
	}

	s.testCases[len(s.testCases)-1].Verdict = verdict
}

// True for the event string from the first line of a test case.
func isStartingEvent(event string) bool {
	return event == "START"
}

// True for the event string from the final line of a test case.
func isFinalEvent(event string) bool {
	return strings.HasPrefix(event, verdictStringPrefix)
}

// True for an event string that may contain a failure/warning reason.
func isStatusUpdateEvent(event string) bool {
	switch event {
	case "FAIL", "WARN", "ERROR", "ABORT", "TEST_NA":
		return true
	}
	return false
}

// isLegalTestCaseName filters out uninformative execution steps.
func isLegalTestCaseName(name string) bool {
	switch name {
	case "reboot", undefinedName, "":
		return false
	}
	return true
}

// parseVerdict converts a verdict string from status.log (e.g. "END GOOD",
// "END FAIL" etc) into a Verdict proto.
func parseVerdict(verdict string) skylab_test_runner.Result_Autotest_TestCase_Verdict {
	// Remove "END " prefix.
	switch verdict[len(verdictStringPrefix):] {
	case "GOOD", "WARN":
		return skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS
	}
	// TODO(crbug.com/846770): deal with TEST_NA separately.
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
