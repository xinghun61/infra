// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"net/url"
	"testing"

	"infra/appengine/test-results/model"
	"infra/monitoring/client"
	"infra/monitoring/client/test"
	"infra/monitoring/messages"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/auth/authtest"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestStepFailureAlerts(t *testing.T) {
	c := gaetesting.TestingContext()
	c = authtest.MockAuthConfig(c)
	c = gologger.StdConfig.Use(c)
	testResultsFake := test.NewFakeServer()
	defer testResultsFake.Server.Close()
	finditFake := test.NewFakeServer()
	defer finditFake.Server.Close()

	c = client.WithFindit(c, finditFake.Server.URL)

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
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
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
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
							},
							"test_b": map[string]interface{}{
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
							},
							"test_c": map[string]interface{}{
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
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
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
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
					name: "test step failure with weird step name on perf",
					failures: []*messages.BuildStep{
						{
							Master: &messages.MasterLocation{URL: url.URL{
								Scheme: "https",
								Host:   "build.chromium.org",
								Path:   "/p/chromium.perf",
							}},
							Build: &messages.Build{
								BuilderName: "fake_builder",
							},
							Step: &messages.Step{
								Name: "something_tests on windows_7 on Intel GPU",
								Logs: [][]interface{}{
									{
										"swarming.summary",
										"foo",
									},
								},
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
								"expected":      "PASS",
								"actual":        "FAIL PASS",
								"is_unexpected": false,
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
								"expected":      "PASS",
								"actual":        "FAIL",
								"is_unexpected": true,
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

			for _, test := range tests {
				test := test
				Convey(test.name, func() {
					newC := client.WithTestResults(c, testResultsFake.Server.URL)
					testResultsFake.JSONResponse = test.testResults

					// knownResults determines what tests the test results server knows about. Set
					// this up so that we don't quit early.
					knownResults := model.BuilderData{}
					if test.testResults != nil {
						for _, failure := range test.failures {
							knownResults.Masters = append(knownResults.Masters, model.Master{
								Name: failure.Master.Name(),
								Tests: map[string]*model.Test{
									GetTestSuite(failure): {
										Builders: []string{failure.Build.BuilderName},
									},
								},
							})
						}
					}

					testResultsFake.PerURLResponse = map[string]interface{}{
						"/data/builders": knownResults,
					}
					finditFake.JSONResponse = &client.FinditAPIResponse{Results: test.finditResults}
					gotResult, gotErr := testFailureAnalyzer(newC, test.failures)
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
				want:     []string{"FAIL"},
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
			{
				name:     "Flaky PASS",
				expected: []string{"PASS", "FAIL"},
				actual:   []string{"PASS"},
				want:     []string{},
			},
			{
				name:     "Flaky CRASH",
				expected: []string{"PASS", "FAIL"},
				actual:   []string{"CRASH"},
				want:     []string{"CRASH"},
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
			s.Step.Logs = [][]interface{}{
				{
					"swarming.summary",
					"foo",
				},
			}
			Convey("with suffixes", func() {
				s.Step.Name = "battor.power_cases on Intel GPU on Linux"
				So(GetTestSuite(s), ShouldEqual, "battor.power_cases")
			})
			Convey("C++ test with suffixes", func() {
				s.Step.Name = "performance_browser_tests on Intel GPU on Linux"
				So(GetTestSuite(s), ShouldEqual, "performance_browser_tests")
			})
			Convey("not a test", func() {
				s.Step.Logs = nil
				s.Step.Name = "something_random"
				So(GetTestSuite(s), ShouldEqual, "")
			})
		})
	})
}
