// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"fmt"
	"strings"

	"infra/monitoring/client"
)

// TestFailureAnalyzer determines the reasons, if any, for a test step failure.
type TestFailureAnalyzer struct {
	Reader client.Reader
}

// Analyze returns the reasons, if any, for the step if it was a test failure. Also returns
// whether or not the analyzer applied to the failure and any error in encountered while
// running.
func (a *TestFailureAnalyzer) Analyze(f stepFailure) (*StepAnalyzerResult, error) {
	ret := &StepAnalyzerResult{}

	name := f.step.Name
	s := strings.Split(name, " ")

	// Android tests add Instrumentation test as a prefix to the step name :/
	if len(s) > 2 && s[0] == "Instrumentation" && s[1] == "test" {
		name = s[2]
		s = []string{name}
	}
	// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
	// term before the space, if there is one.
	if !(strings.HasSuffix(s[0], "tests") || strings.HasSuffix(s[0], "test_apk")) {
		return ret, nil
	}
	ret.Recognized = true

	testResults, err := a.Reader.TestResults(f.master, f.builderName, name, f.build.Number)
	if err != nil {
		ret.Reasons = append(ret.Reasons, name)
		return ret, fmt.Errorf("Error fetching test results: %v", err)
	}

	if len(testResults.Tests) == 0 {
		return ret, fmt.Errorf("No test results for %v", f)
	}

	for testName, testResults := range testResults.Tests {
		res, ok := testResults.(map[string]interface{})
		if !ok {
			errLog.Printf("Couldn't convert test results to map: %s", testName)
			continue
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
				ret.Reasons = append(ret.Reasons, testName)
			}
			continue
		}

		// res is not a simple top-level test result, so recurse to find
		// the actual results.
		ue, err := traverseResults(testName, res)
		if err != nil {
			return nil, err
		}

		for _, e := range ue {
			ret.Reasons = append(ret.Reasons, e)
		}
	}
	return ret, nil
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
