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
	if !strings.HasSuffix(f.step.Name, "tests") {
		return ret, nil
	}
	ret.Recognized = true

	testResults, err := a.Client.TestResults(f.masterName, f.builderName, f.step.Name, f.build.Number)
	if err != nil {
		return ret, fmt.Errorf("Error fetching test results: %v", err)
	}

	if len(testResults.Tests) == 0 {
		log.Errorf("No test results for %v", f)
	}
	log.Infof("%d test results", len(testResults.Tests))

	for testName, testResults := range testResults.Tests {
		// This string splitting logic was copied from builder_alerts.
		// I'm not sure it's really necessary since the strings appear to always
		// be either "PASS" or "FAIL" in practice.
		expected := strings.Split(testResults.Expected, " ")
		actual := strings.Split(testResults.Actual, " ")
		ue := unexpected(expected, actual)
		if len(ue) > 0 {
			ret.Reasons = append(ret.Reasons, testName)
		}
	}
	return ret, nil
}
