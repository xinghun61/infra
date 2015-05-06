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
	Client client.Client
}

// Analyze returns the reasons, if any, for the step if it was a test failure. Also returns
// whether or not the analyzer applied to the failure and any error in encountered while
// running.
func (a *TestFailureAnalyzer) Analyze(f stepFailure) (*StepAnalyzerResult, error) {
	ret := &StepAnalyzerResult{}
	// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
	// term before the space, if there is one.
	s := strings.Split(f.step.Name, " ")
	if !strings.HasSuffix(s[0], "tests") {
		return ret, nil
	}
	ret.Recognized = true

	testResults, err := a.Client.TestResults(f.masterName, f.builderName, f.step.Name, f.build.Number)
	if err != nil {
		ret.Reasons = append(ret.Reasons, f.step.Name)
		return ret, fmt.Errorf("Error fetching test results: %v", err)
	}

	if len(testResults.Tests) == 0 {
		return ret, fmt.Errorf("No test results for %v", f)
	}

	for testName, testResults := range testResults.Tests {
		res, ok := testResults.(map[string]interface{})
		if !ok {
			log.Errorf("Couldn't convert test results to map: %s", testName)
			continue
		}

		// If res is a simple top-level test result, just check it here.
		if res["expected"] != nil || res["actual"] != nil {
			expected := strings.Split(res["expected"].(string), " ")
			actual := strings.Split(res["actual"].(string), " ")
			ue := unexpected(expected, actual)
			if len(ue) > 0 && res["bugs"] == nil {
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
		if len(ue) > 0 {
			// Don't give too many reasons, just the top level test/suite names.
			// TODO: figure out a way to coalesce the unexpected results list into
			// something compact but still meaningful in an alerting context.
			ret.Reasons = append(ret.Reasons, testName)
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

		expected := strings.Split(res["expected"].(string), " ")
		actual := strings.Split(res["actual"].(string), " ")
		ue := unexpected(expected, actual)
		if len(ue) > 0 && res["bugs"] == nil {
			ret = append(ret, fmt.Sprintf("%s/%s: %+v vs %+v", parent, testName, expected, actual))
		}
	}
	return ret, nil
}
