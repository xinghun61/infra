// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFullResult(t *testing.T) {
	t.Parallel()

	Convey("TestFullResult", t, func() {
		runtime := 20.9
		unexpected := true

		leaf := FullTestLeaf{
			Actual:     []string{"PASS", "AUDIO", "CRASH"},
			Expected:   []string{"PASS", "CRASH"},
			Runtime:    &runtime,
			Bugs:       []string{"crbug.com/700", "crbug.com/900"},
			Unexpected: &unexpected,
			Artifacts:  map[string][]string{"image": []string{"foo.png", "bar.png"}},
		}

		ft := FullTest{
			"foo": &FullTestLeaf{
				Actual:   []string{"FLAKY"},
				Expected: []string{"FLAKY"},
			},
			"bar": &FullTestLeaf{
				Actual:   []string{"IMAGE"},
				Expected: []string{"CRASH"},
			},
			"baz": FullTest{
				"qux": FullTest{
					"baaz": &FullTestLeaf{
						Actual:   []string{"CRASH"},
						Expected: []string{"CRASH", "AUDIO"},
					},
				},
				"baax": &leaf,
			},
		}

		chromiumrev := "45000"

		fr := FullResult{
			Version:      4,
			Builder:      "foo_builder",
			BuildNumber:  Number(1000),
			SecondsEpoch: 6400000000,
			Tests:        ft,
			FailuresByType: map[string]int{
				"A": 5,
				"Q": 11,
			},
			ChromiumRev: &chromiumrev,
			TestLocations: &map[string]TestLocation{
				"Foo.Bar": {
					File: "foo/file.cc",
					Line: 123,
				},
				"Foo.Baz": {
					File: "foo/file.cc",
					Line: 452,
				},
			},
		}

		Convey("FullTestLeaf", func() {
			Convey("Marshal followed by unmarshal returns original", func() {
				b, err := json.Marshal(&leaf)
				So(err, ShouldBeNil)
				var actual FullTestLeaf
				So(json.Unmarshal(b, &actual), ShouldBeNil)
				So(actual, ShouldResemble, leaf)
			})
		})

		Convey("FullTest", func() {
			Convey("Marshal followed by unmarshal returns original", func() {
				b, err := json.Marshal(&ft)
				So(err, ShouldBeNil)
				var actual FullTest
				So(json.Unmarshal(b, &actual), ShouldBeNil)
				So(actual, ShouldResemble, ft)
			})

			Convey("Flatten", func() {
				Convey("basic 1", func() {
					expected := FlatTest{
						"foo": &FullTestLeaf{
							Actual:   []string{"FLAKY"},
							Expected: []string{"FLAKY"},
						},
						"bar": &FullTestLeaf{
							Actual:   []string{"IMAGE"},
							Expected: []string{"CRASH"},
						},
						"baz/qux/baaz": &FullTestLeaf{
							Actual:   []string{"CRASH"},
							Expected: []string{"CRASH", "AUDIO"},
						},
						"baz/baax": &FullTestLeaf{
							Actual:     []string{"PASS", "AUDIO", "CRASH"},
							Expected:   []string{"PASS", "CRASH"},
							Runtime:    &runtime,
							Bugs:       []string{"crbug.com/700", "crbug.com/900"},
							Unexpected: &unexpected,
							Artifacts:  map[string][]string{"image": []string{"foo.png", "bar.png"}},
						},
					}
					So(ft.Flatten("/"), ShouldResemble, expected)
				})

				Convey("basic 2", func() {
					ft := FullTest{
						"b": &FullTestLeaf{
							Actual:   []string{"FAIL", "PASS"},
							Expected: []string{"..."},
						},
						"a": FullTest{
							"1": &FullTestLeaf{
								Actual:   []string{"..."},
								Expected: []string{"SKIP"},
							},
							"2": &FullTestLeaf{
								Actual:   []string{"..."},
								Expected: []string{"..."},
							},
						},
					}
					expected := FlatTest{
						"b": &FullTestLeaf{
							Actual:   []string{"FAIL", "PASS"},
							Expected: []string{"..."},
						},
						"a.1": &FullTestLeaf{
							Actual:   []string{"..."},
							Expected: []string{"SKIP"},
						},
						"a.2": &FullTestLeaf{
							Actual:   []string{"..."},
							Expected: []string{"..."},
						},
					}
					So(ft.Flatten("."), ShouldResemble, expected)
				})
			})
		})

		Convey("FullResult", func() {
			Convey("Marshal followed by unmarshal returns original", func() {
				b, err := json.Marshal(&fr)
				So(err, ShouldBeNil)
				var actual FullResult
				So(json.Unmarshal(b, &actual), ShouldBeNil)
				So(actual, ShouldResemble, fr)
			})
		})

		Convey("AggregateResult", func() {
			Convey("basic converion", func() {
				aggr, err := fr.AggregateResult()
				So(err, ShouldBeNil)
				So(aggr, ShouldResemble, AggregateResult{
					Version: ResultsVersion,
					Builder: fr.Builder,
					BuilderInfo: &BuilderInfo{
						SecondsEpoch: []float64{6400000000},
						BuildNumbers: []Number{1000},
						FailureMap:   FailureLongNames,
						Tests: AggregateTest{
							"foo": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "L"}},
								Runtimes: []RuntimeSummary{{1, 0}},
								Expected: []string{"FLAKY"},
							},
							"bar": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "I"}},
								Runtimes: []RuntimeSummary{{1, 0}},
								Expected: []string{"CRASH"},
							},
							"baz": AggregateTest{
								"qux": AggregateTest{
									"baaz": &AggregateTestLeaf{
										Results:  []ResultSummary{{1, "C"}},
										Runtimes: []RuntimeSummary{{1, 0}},
										Expected: []string{"CRASH", "AUDIO"},
									},
								},
								"baax": &AggregateTestLeaf{
									Results:  []ResultSummary{{1, "PAC"}},
									Runtimes: []RuntimeSummary{{1, 21}},
									Expected: []string{"PASS", "CRASH"},
									Bugs:     []string{"crbug.com/700", "crbug.com/900"},
								},
							},
						},
						FailuresByType: map[string][]int{
							"A": {5},
							"Q": {11},
						},
						ChromeRevs: []string{"45000"},
					},
				})
			})
		})
	})
}
