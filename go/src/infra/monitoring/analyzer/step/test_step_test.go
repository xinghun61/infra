// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"net/url"
	"testing"

	"golang.org/x/net/context"

	"infra/monitoring/client"
	"infra/monitoring/client/test"
	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestStepFailureAlerts(t *testing.T) {
	Convey("test TestFailureAnalyzer", t, func() {
		maxFailedTests = 2
		Convey("analyze", func() {
			tests := []struct {
				name          string
				failures      []*messages.BuildStep
				testResults   *messages.TestResults
				finditResults []*messages.FinditResult
				wantResult    []messages.ReasonRaw
				wantErr       error
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
					finditResults: []*messages.FinditResult{
						{
							TestName:    "test_a",
							IsFlakyTest: false,
							SuspectedCLs: []messages.SuspectCL{
								{
									RepoName:       "repo",
									Revision:       "deadbeef",
									CommitPosition: 1234,
								},
							},
						},
					},
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{"test_a"},
							StepName:  "something_tests",
							Tests: []testWithResult{
								{
									TestName: "test_a",
									IsFlaky:  false,
									SuspectedCLs: []messages.SuspectCL{
										{
											RepoName:       "repo",
											Revision:       "deadbeef",
											CommitPosition: 1234,
										},
									},
								},
							},
						},
					},
				},
				{
					name: "test step failure (too many failures)",
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
							"test_b": map[string]interface{}{
								"expected": "PASS",
								"actual":   "FAIL",
							},
							"test_c": map[string]interface{}{
								"expected": "PASS",
								"actual":   "FAIL",
							},
						},
					},
					finditResults: []*messages.FinditResult{
						{
							TestName:    "test_a",
							IsFlakyTest: false,
							SuspectedCLs: []messages.SuspectCL{
								{
									RepoName:       "repo",
									Revision:       "deadbeef",
									CommitPosition: 1234,
								},
							},
						},
						{
							TestName:    "test_b",
							IsFlakyTest: false,
							SuspectedCLs: []messages.SuspectCL{
								{
									RepoName:       "repo",
									Revision:       "deadbeef",
									CommitPosition: 1234,
								},
							},
						},
					},
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{tooManyFailuresText, "test_a", "test_b"},
							StepName:  "something_tests",
							Tests: []testWithResult{
								{
									TestName: "test_a",
									IsFlaky:  false,
									SuspectedCLs: []messages.SuspectCL{
										{
											RepoName:       "repo",
											Revision:       "deadbeef",
											CommitPosition: 1234,
										},
									},
								},
								{
									TestName: "test_b",
									IsFlaky:  false,
									SuspectedCLs: []messages.SuspectCL{
										{
											RepoName:       "repo",
											Revision:       "deadbeef",
											CommitPosition: 1234,
										},
									},
								},
								{
									TestName: tooManyFailuresText,
									IsFlaky:  false,
								},
							},
						},
					},
				},
				{
					name: "test step failure with weird step name",
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
								Name: "something_tests on windows_7",
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
					finditResults: []*messages.FinditResult{
						{
							TestName:    "test_a",
							IsFlakyTest: false,
							SuspectedCLs: []messages.SuspectCL{
								{
									RepoName:       "repo",
									Revision:       "deadbeef",
									CommitPosition: 1234,
								},
							},
						},
					},
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{"test_a"},
							StepName:  "something_tests",
							Tests: []testWithResult{
								{
									TestName: "test_a",
									IsFlaky:  false,
									SuspectedCLs: []messages.SuspectCL{
										{
											RepoName:       "repo",
											Revision:       "deadbeef",
											CommitPosition: 1234,
										},
									},
								},
							},
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
				{
					name: "test findit found flaky",
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
					finditResults: []*messages.FinditResult{
						{
							TestName:     "test_a",
							IsFlakyTest:  true,
							SuspectedCLs: []messages.SuspectCL{},
						},
					},
					wantResult: []messages.ReasonRaw{
						&testFailure{
							TestNames: []string{"test_a"},
							StepName:  "something_tests",
							Tests: []testWithResult{
								{
									TestName:     "test_a",
									IsFlaky:      true,
									SuspectedCLs: []messages.SuspectCL{},
								},
							},
						},
					},
				},
			}

			mc := &test.MockReader{}
			ctx := client.WithReader(context.Background(), mc)

			for _, test := range tests {
				test := test
				Convey(test.name, func() {
					mc.TestResultsValue = test.testResults
					mc.FinditResults = test.finditResults
					gotResult, gotErr := testFailureAnalyzer(ctx, test.failures)
					So(gotErr, ShouldEqual, test.wantErr)
					So(gotResult, ShouldResemble, test.wantResult)
				})
			}
		})
	})
}

func TestUnexpected(t *testing.T) {
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

func TestGetTestSuite(t *testing.T) {
	Convey("GetTestSuite", t, func() {
		s := &messages.BuildStep{
			Step: &messages.Step{
				Name: "thing_tests",
			},
		}
		url, err := url.Parse("https://build.chromium.org/p/chromium.linux")
		So(err, ShouldBeNil)
		s.Master = &messages.MasterLocation{
			URL: *url,
		}
		Convey("basic", func() {
			So(GetTestSuite(s), ShouldEqual, "thing_tests")
		})
		Convey("with suffixes", func() {
			s.Step.Name = "thing_tests on Intel GPU on Linux"
			So(GetTestSuite(s), ShouldEqual, "thing_tests")
		})
		Convey("on perf", func() {
			url, err := url.Parse("https://build.chromium.org/p/chromium.perf")
			So(err, ShouldBeNil)
			s.Master = &messages.MasterLocation{
				URL: *url,
			}
			Convey("with suffixes", func() {
				s.Step.Name = "battor.power_cases on Intel GPU on Linux"
				So(GetTestSuite(s), ShouldEqual, "battor.power_cases")
			})
			Convey("not a test", func() {
				s.Step.Name = "something_random"
				So(GetTestSuite(s), ShouldEqual, "")
			})
		})
	})
}
