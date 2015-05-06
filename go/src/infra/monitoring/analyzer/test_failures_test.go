// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"infra/monitoring/messages"
	"reflect"
	"testing"
)

func TestTestStepFailureAlerts(t *testing.T) {
	tests := []struct {
		name        string
		failure     stepFailure
		testResults *messages.TestResults
		wantResult  *StepAnalyzerResult
		wantErr     error
	}{
		{
			name:       "empty",
			wantResult: &StepAnalyzerResult{},
		},
		{
			name: "non-test failure",
			failure: stepFailure{
				masterName:  "fake.master",
				builderName: "fake_builder",
				step: messages.Steps{
					Name: "tests_compile",
				},
			},
			wantResult: &StepAnalyzerResult{},
		},
		{
			name: "test step failure",
			failure: stepFailure{
				masterName:  "fake.master",
				builderName: "fake_builder",
				step: messages.Steps{
					Name: "something_tests",
				},
			},
			testResults: &messages.TestResults{
				Tests: map[string]interface{}{
					"test_a": map[string]interface{}{
						"expected": "PASS",
						"actual":   "FAIL",
					},
				},
			},
			wantResult: &StepAnalyzerResult{
				Reasons:    []string{"test_a"},
				Recognized: true,
			},
		},
	}

	mc := &mockClient{}
	a := &TestFailureAnalyzer{mc}

	for _, test := range tests {
		mc.testResults = test.testResults
		gotResult, gotErr := a.Analyze(test.failure)
		if !reflect.DeepEqual(gotResult, test.wantResult) {
			t.Errorf("%s failed.\n\tGot:\n\t%+v\n\twant:\n\t%+v.", test.name, gotResult, test.wantResult)
		}
		if !reflect.DeepEqual(gotErr, test.wantErr) {
			t.Errorf("%s failed. Got: %+v want: %+v.", test.name, gotErr, test.wantErr)
		}
	}
}
