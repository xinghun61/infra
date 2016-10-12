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

func TestTraverseResults(t *testing.T) {
	Convey("empty", t, func() {
		s, err := traverseResults("", nil)
		So(len(s), ShouldEqual, 0)
		So(err, ShouldEqual, nil)
	})

	Convey("recurse", t, func() {
		s, err := traverseResults("", map[string]interface{}{
			"test1": map[string]interface{}{
				"subtest1": map[string]interface{}{
					"expected": "PASS",
					"actual":   "FAIL",
				},
			},
		})
		So(len(s), ShouldEqual, 0)
		So(err, ShouldEqual, nil)
	})

	Convey("recurse, results", t, func() {
		s, err := traverseResults("", map[string]interface{}{
			"test1": map[string]interface{}{
				"subtest1": map[string]interface{}{
					"expected":      "PASS",
					"actual":        "FAIL",
					"is_unexpected": true,
				},
			},
		})
		So(len(s), ShouldEqual, 1)
		So(err, ShouldEqual, nil)
	})
}

func TestBasicFailure(t *testing.T) {
	Convey("basicFailure", t, func() {
		bf := &basicFailure{Name: "basic"}
		title := bf.Title([]*messages.BuildStep{
			{
				Master: &messages.MasterLocation{},
				Build:  &messages.Build{BuilderName: "basic.builder"},
				Step:   &messages.Step{Name: "step"},
			},
		})

		So(title, ShouldEqual, "step failing on /basic.builder")

		So(bf.Signature(), ShouldEqual, bf.Name)
		So(bf.Kind(), ShouldEqual, "basic")
	})
}
