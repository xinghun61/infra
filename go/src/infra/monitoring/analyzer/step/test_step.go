// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"fmt"
	"sort"
	"strings"

	"infra/monitoring/client"
	"infra/monitoring/messages"
)

type testFailure struct {
	// Could be more detailed about test failures. For instance, we could
	// indicate expected vs. actual result.
	TestNames []string `json:"test_names"`
	StepName  string
}

func (t *testFailure) Signature() string {
	return strings.Join(append([]string{t.StepName}, t.TestNames...), ",")
}

func (t *testFailure) Kind() string {
	return "test"
}

func (t *testFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("test %s failing on %s/%s", f.Step.Name, f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("test %s failing on %d builders", f.Step.Name, len(bses))
}

// testFailureAnalyzer analyzes steps to see if there is any data in the tests
// server which corresponds to the failure.
func testFailureAnalyzer(reader client.Reader, fs []*messages.BuildStep) ([]messages.ReasonRaw, []error) {
	results := make([]messages.ReasonRaw, len(fs))

	for i, f := range fs {
		rslt, err := testAnalyzeFailure(reader, f)
		if err != nil {
			return nil, []error{err}
		}

		results[i] = rslt
	}

	return results, nil
}

func testAnalyzeFailure(reader client.Reader, f *messages.BuildStep) (messages.ReasonRaw, error) {
	failedTests, err := getTestNames(reader, f)
	if err != nil {
		return nil, err
	}

	if failedTests != nil {
		sortedNames := failedTests
		sort.Strings(sortedNames)
		return &testFailure{
			TestNames: failedTests,
			StepName:  f.Step.Name,
		}, nil
	}

	return nil, nil
}

func getTestNames(reader client.Reader, f *messages.BuildStep) ([]string, error) {
	name := f.Step.Name
	s := strings.Split(name, " ")
	failedTests := []string{name}

	// Android tests add Instrumentation test as a prefix to the step name :/
	if len(s) > 2 && s[0] == "Instrumentation" && s[1] == "test" {
		name = s[2]
		s = []string{name}
	}
	// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
	// term before the space, if there is one.
	if !(strings.HasSuffix(s[0], "tests") || strings.HasSuffix(s[0], "test_apk")) {
		return nil, nil
	}

	testResults, err := reader.TestResults(f.Master, f.Build.BuilderName, name, f.Build.Number)
	if err != nil {
		return failedTests, fmt.Errorf("Error fetching test results: %v", err)
	}

	if len(testResults.Tests) == 0 {
		return failedTests, fmt.Errorf("No test results for %v", f)
	}

	for testName, testResults := range testResults.Tests {
		res, ok := testResults.(map[string]interface{})
		if !ok {
			return nil, err
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
			return nil, err
		}

		failedTests = append(failedTests, ue...)
	}
	return failedTests, nil
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
