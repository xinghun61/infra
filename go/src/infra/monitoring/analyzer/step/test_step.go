// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"fmt"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"infra/monitoring/client"
	"infra/monitoring/messages"
)

type testFailure struct {
	// Could be more detailed about test failures. For instance, we could
	// indicate expected vs. actual result.
	//FIXME: Merge TestNames and Tests.
	TestNames []string `json:"test_names"`
	//FIXME: Rename to TestSuite (needs to be synchronized with SOM)
	StepName string           `json:"step"`
	Tests    []testWithResult `json:"tests"`
}

// testWithResult stores the information provided by Findit for a specific test,
// for example if the test is flaky or is there a culprit for the test failure.
type testWithResult struct {
	TestName     string               `json:"test_name"`
	IsFlaky      bool                 `json:"is_flaky"`
	SuspectedCLs []messages.SuspectCL `json:"suspected_cls"`
}

func (t *testFailure) Signature() string {
	return strings.Join(append([]string{t.StepName}, t.TestNames...), ",")
}

func (t *testFailure) Kind() string {
	return "test"
}

func (t *testFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (t *testFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("%s failing on %s/%s", GetTestSuite(f.Step), f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("%s failing on %d builders", GetTestSuite(f.Step), len(bses))
}

// testFailureAnalyzer analyzes steps to see if there is any data in the tests
// server which corresponds to the failure.
func testFailureAnalyzer(ctx context.Context, fs []*messages.BuildStep) ([]messages.ReasonRaw, []error) {
	results := make([]messages.ReasonRaw, len(fs))

	for i, f := range fs {
		rslt, err := testAnalyzeFailure(ctx, f)
		if err != nil {
			return nil, []error{err}
		}

		results[i] = rslt
	}

	return results, nil
}

// tests is a slice of tests with Findit results.
type tests []testWithResult

func (slice tests) Len() int {
	return len(slice)
}

func (slice tests) Less(i, j int) bool {
	return (len(slice[i].SuspectedCLs) > 0 && len(slice[j].SuspectedCLs) == 0) || (slice[i].IsFlaky && !slice[j].IsFlaky)
}

func (slice tests) Swap(i, j int) {
	slice[i], slice[j] = slice[j], slice[i]
}

func testAnalyzeFailure(ctx context.Context, f *messages.BuildStep) (messages.ReasonRaw, error) {
	suiteName, failedTests, err := getTestNames(ctx, f)
	if err != nil {
		return nil, err
	}

	testsWithFinditResults, err := getFinditResultsForTests(ctx, f, failedTests)
	if err != nil {
		return nil, err
	}

	if failedTests != nil {
		sortedNames := failedTests
		sort.Strings(sortedNames)
		sortedTests := tests(testsWithFinditResults)
		sort.Sort(sortedTests)
		return &testFailure{
			TestNames: sortedNames,
			StepName:  suiteName,
			Tests:     testsWithFinditResults,
		}, nil
	}

	return nil, nil
}

// GetTestSuite returns the name of the test suite executed in a step. Currently, it has
// a bunch of custom logic to parse through all the suffixes added by various recipe code.
// Eventually, it should just read something structured from the step.
// https://bugs.chromium.org/p/chromium/issues/detail?id=674708
func GetTestSuite(step *messages.Step) string {
	testSuite := step.Name
	s := strings.Split(step.Name, " ")

	// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
	// term before the space, if there is one.
	if !(strings.HasSuffix(s[0], "tests") || strings.HasSuffix(s[0], "test_apk")) {
		return testSuite
	}

	// Recipes add a suffix to steps of the OS that it's run on, when the test
	// is swarmed. The step name is formatted like this: "<task title> on <OS>".
	// Added in this code:
	// https://chromium.googlesource.com/chromium/tools/build/+/9ef66559727c320b3263d7e82fb3fcd1b6a3bd55/scripts/slave/recipe_modules/swarming/api.py#846
	if len(s) > 2 && s[1] == "on" {
		testSuite = s[0]
	}

	return testSuite
}

func getTestNames(ctx context.Context, f *messages.BuildStep) (string, []string, error) {
	name := GetTestSuite(f.Step)
	if name == "" {
		return "", nil, nil
	}

	failedTests := []string{}

	testResults, err := client.TestResults(ctx, f.Master, f.Build.BuilderName, name, f.Build.Number)
	if err != nil {
		return name, failedTests, fmt.Errorf("Error fetching test results: %v", err)
	}

	if testResults == nil || len(testResults.Tests) == 0 {
		return name, nil, nil
	}

	for testName, testResults := range testResults.Tests {
		res, ok := testResults.(map[string]interface{})
		if !ok {
			return "", nil, err
		}

		// If res is a simple top-level test result, just check it here.
		if res["expected"] != nil || res["actual"] != nil {
			expected := strings.Split(res["expected"].(string), " ")
			actual := strings.Split(res["actual"].(string), " ")
			ue := unexpected(expected, actual)

			// Could still be a flaky test, so check if last of actual is PASS
			// expected: PASS
			// actual: FAIL PASS
			if len(ue) > 0 && res["bugs"] == nil && actual[len(actual)-1] != "PASS" {
				failedTests = append(failedTests, testName)
			}
			continue
		}

		// res is not a simple top-level test result, so recurse to find
		// the actual results.
		ue, err := traverseResults(testName, res)
		if err != nil {
			return "", nil, err
		}

		failedTests = append(failedTests, ue...)
	}

	if len(failedTests) > 40 {
		// FIXME: Log this
		failedTests = append(failedTests[:40], "...... too many results, data snipped....")
	}

	return name, failedTests, nil
}

// Read Findit results and get suspected cls or check if flaky for each test.
func getFinditResultsForTests(ctx context.Context, f *messages.BuildStep, failedTests []string) ([]testWithResult, error) {
	TestsWithFinditResults := []testWithResult{}

	if failedTests == nil || len(failedTests) == 0 {
		return nil, nil
	}

	name := GetTestSuite(f.Step)
	if name == "" {
		return nil, nil
	}

	finditResults, err := client.Findit(ctx, f.Master, f.Build.BuilderName, f.Build.Number, []string{name})
	if err != nil {
		return nil, fmt.Errorf("while getting findit results: %s", err)
	}
	finditResultsMap := map[string]*messages.FinditResult{}
	for _, result := range finditResults {
		finditResultsMap[result.TestName] = result
	}
	for _, test := range failedTests {
		testResult := testWithResult{
			TestName:     test,
			IsFlaky:      false,
			SuspectedCLs: nil,
		}
		result, ok := finditResultsMap[test]
		if ok {
			testResult = testWithResult{
				TestName:     test,
				IsFlaky:      result.IsFlakyTest,
				SuspectedCLs: result.SuspectedCLs,
			}
		}
		TestsWithFinditResults = append(TestsWithFinditResults, testResult)
	}
	return TestsWithFinditResults, nil
}

// unexpected returns the set of expected xor actual.
func unexpected(expected, actual []string) []string {
	e, a := make(map[string]bool), make(map[string]bool)
	for _, s := range expected {
		e[s] = true
	}
	for _, s := range actual {
		a[s] = true
	}

	ret := []string{}
	for k := range e {
		if !a[k] {
			ret = append(ret, k)
		}
	}

	for k := range a {
		if !e[k] {
			ret = append(ret, k)
		}
	}

	return ret
}

// testResults json is an arbitrarily deep tree, whose nodes are the actual
// test results, so we recurse to find them.
func traverseResults(parent string, testResults map[string]interface{}) ([]string, error) {
	ret := []string{}
	for testName, testResults := range testResults {
		res, ok := testResults.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("Couldn't convert test results to map: %s/%s", parent, testName)
		}
		// First check if results is actually results, or just another branch
		// in the tree of test results
		// Uuuuugly.
		if res["expected"] == nil || res["actual"] == nil {
			// Assume it's a branch.
			res, err := traverseResults(fmt.Sprintf("%s/%s", parent, testName), res)
			if err != nil {
				return ret, err
			}
			ret = append(ret, res...)
			continue
		}

		if ue, ok := res["is_unexpected"]; ok && ue.(bool) && res["actual"] != "PASS" {
			ret = append(ret, fmt.Sprintf("%s/%s", parent, testName))
		}
	}
	return ret, nil
}
