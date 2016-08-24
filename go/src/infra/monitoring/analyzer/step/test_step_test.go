// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"net/url"
	"testing"

	"infra/monitoring/client/test"
	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestStepFailureAlerts(t *testing.T) {
	t.Parallel()

	Convey("test TestFailureAnalyzer", t, func() {
		Convey("analyze", func() {
			tests := []struct {
				name        string
				failures    []*messages.BuildStep
				testResults *messages.TestResults
				wantResult  []messages.ReasonRaw
				wantErr     error
			}{
				{
					name:       "empty",
					wantResult: []messages.ReasonRaw{},
				},
				{
					name: "non-test failure",
					failures: []*messages.BuildStep{
						{
							Master: &messages.MasterLocation{URL: url.URL{
								Scheme: "https",
								Host:   "build.chromium.org",
								Path:   "/p/fake.Master",
							}},
							Build: &messages.Build{
								BuilderName: "fake_builder",
							},
							Step: &messages.Step{
								Name: "tests_compile",
							},
						},
					},
					wantResult: []messages.ReasonRaw{
						nil,
					},
				},
				{
					name: "test step failure",
					failures: []*messages.BuildStep{
						{
							Master: &messages.MasterLocation{URL: url.URL{
								Scheme: "https",
								Host:   "build.chromium.org",
								Path:   "/p/fake.Master",
							}},
							Build: &messages.Build{
								BuilderName: "fake_builder",
							},
							Step: &messages.Step{
								Name: "something_tests",
							},
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
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{"test_a"},
							StepName:  "something_tests",
						},
					},
				},
				{
					name: "flaky",
					failures: []*messages.BuildStep{
						{
							Master: &messages.MasterLocation{URL: url.URL{
								Scheme: "https",
								Host:   "build.chromium.org",
								Path:   "/p/fake.Master",
							}},
							Build: &messages.Build{
								BuilderName: "fake_builder",
							},
							Step: &messages.Step{
								Name: "something_tests",
							},
						},
					},
					testResults: &messages.TestResults{
						Tests: map[string]interface{}{
							"test_a": map[string]interface{}{
								"expected": "PASS",
								"actual":   "FAIL PASS",
							},
						},
					},
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{},
							StepName:  "something_tests",
						},
					},
				},
			}

			mc := &test.MockReader{}

			for _, test := range tests {
				test := test
				Convey(test.name, func() {
					mc.TestResultsValue = test.testResults
					gotResult, gotErr := testFailureAnalyzer(mc, test.failures)
					So(gotErr, ShouldEqual, test.wantErr)
					So(gotResult, ShouldResemble, test.wantResult)
				})
			}
		})
	})
}

func TestUnexpected(t *testing.T) {
	t.Parallel()

	Convey("unexpected", t, func() {
		tests := []struct {
			name                   string
			expected, actual, want []string
		}{
			{
				name: "empty",
				want: []string{},
			},
			{
				name:     "extra FAIL",
				expected: []string{"PASS"},
				actual:   []string{"FAIL"},
				want:     []string{"PASS", "FAIL"},
			},
			{
				name:     "FAIL FAIL",
				expected: []string{"FAIL"},
				actual:   []string{"FAIL"},
				want:     []string{},
			},
			{
				name:     "PASS PASS",
				expected: []string{"PASS"},
				actual:   []string{"PASS"},
				want:     []string{},
			},
		}

		for _, test := range tests {
			test := test
			Convey(test.name, func() {
				got := unexpected(test.expected, test.actual)
				So(got, ShouldResemble, test.want)
			})
		}
	})
}
