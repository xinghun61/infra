// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCleanJSON(t *testing.T) {
	Convey("CleanJSON", t, func() {
		data := `{"foo":"bar"}`

		Convey("Strips prefix and suffix", func() {
			r := bytes.NewReader([]byte(`ADD_RESULTS(` + data + `);`))
			res, err := CleanJSON(r)
			So(err, ShouldBeNil)
			b, err := ioutil.ReadAll(res)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, data)
		})

		Convey("Returns original when prefix and suffix are absent", func() {
			r := bytes.NewReader([]byte(data))
			res, err := CleanJSON(r)
			So(err, ShouldBeNil)
			b, err := ioutil.ReadAll(res)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, data)
		})
	})
}

func TestResultSummary(t *testing.T) {
	t.Parallel()

	Convey("ResultSummary", t, func() {
		rs := ResultSummary{1, "F"}
		b := `[1,"F"]`

		Convey("Unmarshal", func() {
			Convey("Simple", func() {
				var actual ResultSummary
				So(json.Unmarshal([]byte(b), &actual), ShouldBeNil)
				So(actual, ShouldResemble, rs)
			})

			Convey("Wrong type", func() {
				b := `[20, 100]`
				So(json.Unmarshal([]byte(b), &ResultSummary{}), ShouldNotBeNil)
			})

			Convey("Wrong length (longer)", func() {
				b := `[20.0, "A", "B"]`
				So(json.Unmarshal([]byte(b), &ResultSummary{}), ShouldNotBeNil)
			})

			Convey("Wrong length (shorter)", func() {
				b := `[]`
				So(json.Unmarshal([]byte(b), &ResultSummary{}), ShouldNotBeNil)
				b = `[2]`
				So(json.Unmarshal([]byte(b), &ResultSummary{}), ShouldNotBeNil)
			})
		})

		Convey("Marshal", func() {
			Convey("Simple", func() {
				actual, err := json.Marshal(&rs)
				So(err, ShouldBeNil)
				So(actual, ShouldResemble, []byte(b))
			})
		})
	})
}

func TestRuntimeSummary(t *testing.T) {
	t.Parallel()

	Convey("RuntimeSummary", t, func() {
		rs := RuntimeSummary{1, 0.001}

		Convey("Unmarshal", func() {
			Convey("Simple floats", func() {
				var actual RuntimeSummary
				b := `[1,0.001]`
				So(json.Unmarshal([]byte(b), &actual), ShouldBeNil)
				So(actual, ShouldResemble, rs)
			})

			Convey("Wrong type", func() {
				b := `["20.0", 3.2]`
				So(json.Unmarshal([]byte(b), &RuntimeSummary{}), ShouldNotBeNil)
			})

			Convey("Wrong length (longer)", func() {
				b := `[20.0, 3.2, 3]`
				So(json.Unmarshal([]byte(b), &RuntimeSummary{}), ShouldNotBeNil)
			})

			Convey("Wrong length (shorter)", func() {
				b := `[]`
				So(json.Unmarshal([]byte(b), &RuntimeSummary{}), ShouldNotBeNil)
				b = `[2]`
				So(json.Unmarshal([]byte(b), &RuntimeSummary{}), ShouldNotBeNil)
			})
		})

		Convey("Marshal", func() {
			Convey("Simple", func() {
				b := `[1,0.001]`
				actual, err := json.Marshal(&rs)
				So(err, ShouldBeNil)
				So(actual, ShouldResemble, []byte(b))
			})
		})
	})
}

func TestAggregateTestLeaf(t *testing.T) {
	t.Parallel()

	Convey("AggregateTestLeaf", t, func() {
		Convey("Marshal followed by unmarshal returns original", func() {
			truth := &AggregateTestLeaf{
				Results:  []ResultSummary{{1, "A"}},
				Runtimes: []RuntimeSummary{{20, 30.5}},
				Expected: []string{"PASS", "FAIL"},
				Bugs:     []string{"crbug.com/365, crbug.com/1080"},
			}
			b, err := json.Marshal(truth)
			So(err, ShouldBeNil)
			actual := &AggregateTestLeaf{}
			So(json.Unmarshal(b, actual), ShouldBeNil)
			So(actual, ShouldResemble, truth)
		})
	})
}

func TestAggregateTest(t *testing.T) {
	t.Parallel()

	Convey("AggregateTest", t, func() {
		Convey("Marshal followed by unmarshal returns original", func() {
			truth := AggregateTest{
				"foo": AggregateTest{
					"bar": &AggregateTestLeaf{
						Results:  []ResultSummary{{1, "A"}},
						Runtimes: []RuntimeSummary{{20, 30.5}},
						Expected: []string{"PASS", "FAIL"},
						Bugs:     []string{"crbug.com/365, crbug.com/1080"},
					},
				},
				"baz": &AggregateTestLeaf{
					Results:  []ResultSummary{{2, "N"}},
					Runtimes: []RuntimeSummary{{20, 4}},
				},
			}
			b, err := json.Marshal(truth)
			So(err, ShouldBeNil)
			var actual AggregateTest
			So(json.Unmarshal(b, &actual), ShouldBeNil)
			So(actual, ShouldResemble, truth)
		})
	})
}

func TestAggregateResult(t *testing.T) {
	t.Parallel()

	Convey("AggregateResult", t, func() {
		Convey("Unmarshal", func() {
			Convey("Unit tests", func() {
				tm := map[string]interface{}{
					"version": 4,
					"foo_builder": map[string]interface{}{
						"blinkRevision":     []string{"100", "200", "0", "-50"},
						"secondsSinceEpoch": []float64{40 << 20, 4 << 20, 400 << 2, -42},
						"chromeRevision": []string{
							"10", "40", "900", "65536", "afd807a", "88da8f4",
						},
						"buildNumbers": []string{"9000", "7500", "-42", "0"},
						"failure_map": map[string]string{
							"A": "Audio", "C": "Crash",
						},
						"num_failures_by_type": map[string][]int{
							"FAIL": {0, 2, 1},
						},
						"tests": map[string]interface{}{},
					},
				}
				marshal := func(m map[string]interface{}) []byte {
					b, err := json.Marshal(m)
					So(err, ShouldBeNil)
					return b
				}
				t := AggregateResult{Builder: "foo_builder"}

				Convey("Version", func() {
					Convey("Invalid version", func() {
						tm["version"] = 9000
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)

						tm["version"] = "a"
						b = marshal(tm)
						err = json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid version", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.Version, ShouldEqual, tm["version"])

						tm["version"] = 0
						b = marshal(tm)
						err = json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.Version, ShouldEqual, 0)
					})
				})

				Convey("Top-level builder key", func() {
					Convey("Wrong builder type", func() {
						tm["foo_builder"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)

						tm["foo_builder"] = []int{}
						b = marshal(tm)
						err = json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Missing builder key", func() {
						delete(tm, "foo_builder")
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid builder", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.Builder, ShouldEqual, "foo_builder")
					})
				})

				Convey("secondsSinceEpoch", func() {
					Convey("Wrong secondsSinceEpoch element type", func() {
						tm["foo_builder"].(map[string]interface{})["secondsSinceEpoch"] =
							[]interface{}{1, 2, "a"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid secondsSinceEpoch", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.SecondsEpoch, ShouldResemble,
							tm["foo_builder"].(map[string]interface{})["secondsSinceEpoch"])
					})
				})

				Convey("blinkRevison", func() {
					Convey("Wrong blinkRevison element type", func() {
						tm["foo_builder"].(map[string]interface{})["blinkRevision"] =
							[]interface{}{"900", "bad"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid blinkRevision", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.BlinkRevs, ShouldResemble, []Number{100, 200, 0, -50})
					})
				})

				Convey("buildNumbers", func() {
					Convey("Wrong buildNumbers element type", func() {
						tm["foo_builder"].(map[string]interface{})["buildNumbers"] =
							[]interface{}{"900", "bad"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Wrong buildNumbers list type", func() {
						tm["foo_builder"].(map[string]interface{})["buildNumbers"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid buildNumbers", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.BuildNumbers, ShouldResemble, []Number{9000, 7500, -42, 0})
					})
				})

				Convey("chromeRevision", func() {
					Convey("Wrong chromeRevision element type", func() {
						tm["foo_builder"].(map[string]interface{})["chromeRevision"] =
							[]interface{}{"900", false, "str"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Valid chromeRevision", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.ChromeRevs, ShouldResemble,
							[]string{"10", "40", "900", "65536", "afd807a", "88da8f4"},
						)
					})
				})

				Convey("num_failures_by_type", func() {
					Convey("num_failures_by_type exists, has wrong type, missing fixableCounts ", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("num_failures_by_type exists, has wrong inner type, missing fixableCounts", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = map[string][]interface{}{"bar": {"baz"}}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("num_failures_by_type exists and is right type", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.FailuresByType, ShouldResemble, tm["foo_builder"].(map[string]interface{})["num_failures_by_type"])
					})

					Convey("num_failures_by_type is invalid, fixableCounts is invalid", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = nil
						tm["foo_builder"].(map[string]interface{})["fixableCounts"] = map[string]string{}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("num_failures_by_type is invalid but fixableCounts is valid", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = nil
						tm["foo_builder"].(map[string]interface{})["fixableCounts"] = []map[string]int{
							{"Q": 1},
							{"Q": 2},
							{"A": 100},
						}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.FailuresByType, ShouldResemble, map[string][]int{
							"FAIL":  {1, 2},
							"AUDIO": {100},
						})
					})
				})
			})

			Convey("Testing with testdata/*.json", func() {
				good, err := ioutil.ReadFile(filepath.Join("testdata", "results.json"))
				So(err, ShouldBeNil)
				t := AggregateResult{}
				So(json.Unmarshal(good, &t), ShouldBeNil)

				Convey("Has correct version", func() {
					So(t.Version, ShouldEqual, 4)
				})

				Convey("Marshal and Unmarshal should be inverse ops", func() {
					var (
						repeater = AggregateResult{Builder: "win_chromium_rel_ng"}
						actual   = AggregateResult{Builder: "win_chromium_rel_ng"}
					)

					So(json.Unmarshal(good, &repeater), ShouldBeNil)
					b, err := json.Marshal(&repeater)
					So(err, ShouldBeNil)

					So(json.Unmarshal(b, &actual), ShouldBeNil)
					So(actual, ShouldResemble, t)
				})
			})

			Convey("Testing with merge issue testdata/*.json", func() {
				// This test is to verify we can recover from incorrectly parsed full_results.json
				// files that have been merged into results.json and results-small.json.
				// Essentially, for a period of time the "artifacts" field was incorrectly
				// interpreted as another branch in the test name trie, and thus its contents
				// were stored as an  AggregateTest instead of a field on AggregateTestLeaf.
				// While the FullResults parser was fixed to stop doing this, we still have
				// broken data to deal with in the Merge step.
				good, err := ioutil.ReadFile(filepath.Join("testdata", "merge-results.json"))
				So(err, ShouldBeNil)
				results := AggregateResult{}
				So(json.Unmarshal(good, &results), ShouldBeNil)

				good, err = ioutil.ReadFile(filepath.Join("testdata", "merge-results-small.json"))
				So(err, ShouldBeNil)
				resultsSmall := AggregateResult{}
				So(json.Unmarshal(good, &resultsSmall), ShouldBeNil)

				good, err = ioutil.ReadFile(filepath.Join("testdata", "merge-full-results.json"))
				So(err, ShouldBeNil)
				fullResults := FullResult{}
				So(json.Unmarshal(good, &fullResults), ShouldBeNil)

				// Verify that we can parse bad old data correctly.
				resultsOctaneNode := results.Tests["octane"].(AggregateTest)
				So(resultsOctaneNode, ShouldNotBeNil)
				resultsLeafNode := resultsOctaneNode["http://chromium.github.io/octane/index.html?auto=1"].(*AggregateTestLeaf)
				So(resultsLeafNode, ShouldNotBeNil)
				So(len(resultsLeafNode.Results), ShouldEqual, 1)

				resultsSmallOctaneNode := resultsSmall.Tests["octane"].(AggregateTest)
				So(resultsSmallOctaneNode, ShouldNotBeNil)
				resultsSmallLeafNode := resultsSmallOctaneNode["http://chromium.github.io/octane/index.html?auto=1"].(*AggregateTestLeaf)
				So(resultsSmallLeafNode, ShouldNotBeNil)
				So(len(resultsSmallLeafNode.Results), ShouldEqual, 1)

				// Now convert the FullResults to aggregate so we can merge.
				fullAgg, err := fullResults.AggregateResult()
				So(err, ShouldBeNil)

				octaneNode := fullAgg.Tests["octane"].(AggregateTest)
				So(octaneNode, ShouldNotBeNil)
				leafNode := octaneNode["http://chromium.github.io/octane/index.html?auto=1"].(*AggregateTestLeaf)
				So(leafNode, ShouldNotBeNil)
				So(len(leafNode.Results), ShouldEqual, 1)

				// Test the merge with bad old data.
				So(results.Merge(&fullAgg), ShouldBeNil)
				So(resultsSmall.Merge(&fullAgg), ShouldBeNil)

				// Verify that the merge actually worked.
				resultsOctaneNode = resultsSmall.Tests["octane"].(AggregateTest)
				So(resultsOctaneNode, ShouldNotBeNil)
				resultsLeafNode = resultsOctaneNode["http://chromium.github.io/octane/index.html?auto=1"].(*AggregateTestLeaf)
				So(resultsLeafNode, ShouldNotBeNil)
				So(len(resultsLeafNode.Results), ShouldEqual, 2)

				resultsSmallOctaneNode = resultsSmall.Tests["octane"].(AggregateTest)
				So(resultsSmallOctaneNode, ShouldNotBeNil)
				resultsSmallLeafNode = resultsSmallOctaneNode["http://chromium.github.io/octane/index.html?auto=1"].(*AggregateTestLeaf)
				So(resultsSmallLeafNode, ShouldNotBeNil)
				So(len(resultsSmallLeafNode.Results), ShouldEqual, 2)
			})
		})
	})
}

func TestMerge(t *testing.T) {
	t.Parallel()

	Convey("Merge", t, func() {
		Convey("AggregateTestLeaf", func() {
			leaf := &AggregateTestLeaf{
				Bugs:     []string{"crbug.com/baz"},
				Expected: []string{"FAIL"},
				Results:  []ResultSummary{{2, "P"}, {30, "F"}},
				Runtimes: []RuntimeSummary{{1, 500}, {4, 750}, {1, 250}},
			}
			x := &AggregateTestLeaf{
				Bugs:     []string{"crbug.com/foo", "crbug.com/bar"},
				Results:  []ResultSummary{{1, "P"}, {42, "X"}},
				Runtimes: []RuntimeSummary{{2, 5000}, {4, 5000}, {8, 6000}},
			}

			Convey("Use x.Bugs, x.Expected", func() {
				x.Expected = []string{"FAIL PASS"}
				So(leaf.Merge(x), ShouldBeNil)
				So(leaf.Bugs, ShouldResemble, x.Bugs)
				So(leaf.Expected, ShouldResemble, x.Expected)
			})

			Convey(`Do not use x.Expected if == "PASS"`, func() {
				x.Expected = []string{"PASS"}
				So(leaf.Merge(x), ShouldBeNil)
				So(leaf.Bugs, ShouldResemble, x.Bugs)
				So(leaf.Expected, ShouldResemble, []string{"FAIL"})
			})

			Convey("Merge matching Results", func() {
				So(leaf.Merge(x), ShouldBeNil)
				So(leaf.Results, ShouldResemble, []ResultSummary{
					{42, "X"},
					{3, "P"},
					{30, "F"},
				})
			})

			Convey("Merge matching Runtimes", func() {
				So(leaf.Merge(x), ShouldBeNil)
				So(leaf.Runtimes, ShouldResemble, []RuntimeSummary{
					{8, 6000},
					{6, 5000},
					{1, 500},
					{4, 750},
					{1, 250},
				})
			})
		})

		Convey("AggregateTest", func() {
			Convey("Join all AggregateTest multi-level", func() {
				at := AggregateTest{
					"foo": &AggregateTestLeaf{
						Results:  []ResultSummary{{10, "P"}},
						Runtimes: []RuntimeSummary{{1, 2}},
					},
					"qux": AggregateTest{
						"experiment": &AggregateTestLeaf{
							Results:  []ResultSummary{{20, "A"}},
							Runtimes: []RuntimeSummary{{3, 5}},
						},
						"paper": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "B"}},
							Runtimes: []RuntimeSummary{{30, 10}},
						},
					},
				}
				x := AggregateTest{
					"bar": &AggregateTestLeaf{
						Results:  []ResultSummary{{20, "F"}},
						Runtimes: []RuntimeSummary{{3, 0}},
					},
					"qux": AggregateTest{
						"paper": &AggregateTestLeaf{
							Results:  []ResultSummary{{6, "F"}},
							Runtimes: []RuntimeSummary{{2, 3}},
						},
						"pencil": &AggregateTestLeaf{
							Results:  []ResultSummary{{75, "Z"}},
							Runtimes: []RuntimeSummary{{15, 60}},
						},
					},
				}
				expected := AggregateTest{
					"foo": &AggregateTestLeaf{
						Results:  []ResultSummary{{1, "N"}, {10, "P"}},
						Runtimes: []RuntimeSummary{{1, 0}, {1, 2}},
					},
					"bar": &AggregateTestLeaf{
						Results:  []ResultSummary{{20, "F"}},
						Runtimes: []RuntimeSummary{{3, 0}},
					},
					"qux": AggregateTest{
						"experiment": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "N"}, {20, "A"}},
							Runtimes: []RuntimeSummary{{1, 0}, {3, 5}},
						},
						"paper": &AggregateTestLeaf{
							Results:  []ResultSummary{{6, "F"}, {1, "B"}},
							Runtimes: []RuntimeSummary{{2, 3}, {30, 10}},
						},
						"pencil": &AggregateTestLeaf{
							Results:  []ResultSummary{{75, "Z"}},
							Runtimes: []RuntimeSummary{{15, 60}},
						},
					},
				}
				So(at.Merge(x), ShouldBeNil)
				So(at, ShouldResemble, expected)
			})

			Convey("Mismatched type", func() {
				Convey("Merge AggregateTestLeaf into AggregateTest", func() {
					at := AggregateTest{
						"foo": AggregateTest{
							"bar": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "P"}},
								Runtimes: []RuntimeSummary{{1, 2}},
							},
						},
					}
					x := AggregateTest{
						"foo": AggregateTest{
							"bar": AggregateTest{
								"baz": &AggregateTestLeaf{
									Results:  []ResultSummary{{20, "F"}},
									Runtimes: []RuntimeSummary{{3, 0}},
								},
							},
						},
					}
					err := at.Merge(x)
					So(err, ShouldNotBeNil)
					So(err.Error(), ShouldContainSubstring, " *AggregateTestLeaf")
				})

				Convey("Merge AggregateTest into AggregateTestLeaf", func() {
					at := AggregateTest{
						"foo": AggregateTest{
							"bar": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "P"}},
								Runtimes: []RuntimeSummary{{1, 2}},
							},
						},
					}
					x := AggregateTest{
						"foo": &AggregateTestLeaf{
							Results:  []ResultSummary{{20, "F"}},
							Runtimes: []RuntimeSummary{{3, 0}},
						},
					}
					err := at.Merge(x)
					So(err, ShouldNotBeNil)
					So(err.Error(), ShouldContainSubstring, " AggregateTest")
				})
			})

			Convey("Merge (all together)", func() {
				at := AggregateTest{
					"presentation": AggregateTest{
						"presentation": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "P"}},
							Runtimes: []RuntimeSummary{{1, 2}},
						},
						"readme": &AggregateTestLeaf{
							Results:  []ResultSummary{{20, "Q"}},
							Runtimes: []RuntimeSummary{{3, 4}},
						},
					},
					"io": AggregateTest{
						"serial": &AggregateTestLeaf{
							Results:  []ResultSummary{{40, "S"}},
							Runtimes: []RuntimeSummary{{8, 9}},
						},
					},
					"hello": AggregateTest{
						"world": AggregateTest{
							"main": &AggregateTestLeaf{
								Results:  []ResultSummary{{50, "T"}},
								Runtimes: []RuntimeSummary{{10, 11}},
							},
						},
					},
				}
				x := AggregateTest{
					"presentation": AggregateTest{
						"presentation": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "A"}},
							Runtimes: []RuntimeSummary{{1, 2}},
						},
						"readme": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "B"}},
							Runtimes: []RuntimeSummary{{1, 2}},
						},
					},
					"io": AggregateTest{
						"analog": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "D"}},
							Runtimes: []RuntimeSummary{{3, 0}},
						},
						"parallel": AggregateTest{
							"duplex": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "E"}},
								Runtimes: []RuntimeSummary{{3, 5}},
							},
							"simplex": &AggregateTestLeaf{
								Results:  []ResultSummary{{60, "H"}},
								Runtimes: []RuntimeSummary{{30, 50}},
							},
						},
					},
					"cool": AggregateTest{
						"world": AggregateTest{
							"main": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "F"}},
								Runtimes: []RuntimeSummary{{3, 6}},
							},
						},
					},
				}
				expected := AggregateTest{
					"presentation": AggregateTest{
						"presentation": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "A"}, {10, "P"}},
							Runtimes: []RuntimeSummary{{2, 2}},
						},
						"readme": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "B"}, {20, "Q"}},
							Runtimes: []RuntimeSummary{{1, 2}, {3, 4}},
						},
					},
					"io": AggregateTest{
						"serial": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "N"}, {40, "S"}},
							Runtimes: []RuntimeSummary{{1, 0}, {8, 9}},
						},
						"analog": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "D"}},
							Runtimes: []RuntimeSummary{{3, 0}},
						},
						"parallel": AggregateTest{
							"duplex": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "E"}},
								Runtimes: []RuntimeSummary{{3, 5}},
							},
							"simplex": &AggregateTestLeaf{
								Results:  []ResultSummary{{60, "H"}},
								Runtimes: []RuntimeSummary{{30, 50}},
							},
						},
					},
					"hello": AggregateTest{
						"world": AggregateTest{
							"main": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "N"}, {50, "T"}},
								Runtimes: []RuntimeSummary{{1, 0}, {10, 11}},
							},
						},
					},
					"cool": AggregateTest{
						"world": AggregateTest{
							"main": &AggregateTestLeaf{
								Results:  []ResultSummary{{10, "F"}},
								Runtimes: []RuntimeSummary{{3, 6}},
							},
						},
					},
				}
				So(at.Merge(x), ShouldBeNil)
				So(at, ShouldResemble, expected)
			})
		})

		Convey("AggregateResult", func() {
			Convey("Basic merge with same test names", func() {
				ag := &AggregateResult{
					Version: ResultsVersion,
					Builder: "foo_builder",
					BuilderInfo: &BuilderInfo{
						SecondsEpoch: []float64{1, 2},
						BlinkRevs:    []Number{3, 4},
						BuildNumbers: []Number{5, 6},
						ChromeRevs:   []string{"a", "1"},
						Tests: AggregateTest{
							"foo": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "A"}, {3, "B"}},
								Runtimes: []RuntimeSummary{{1, 2}, {3, 4}},
							},
						},
						FailureMap: FailureLongNames,
						FailuresByType: map[string][]int{
							"AUDIO": {1, 2, 3, 4},
							"CRASH": {100, 200},
							"LEAKY": {0},
							"PASS":  {5},
						},
					},
				}
				x := &AggregateResult{
					Builder: "foo_builder",
					BuilderInfo: &BuilderInfo{
						SecondsEpoch: []float64{10, 20},
						BlinkRevs:    []Number{30, 40},
						BuildNumbers: []Number{50, 60},
						ChromeRevs:   []string{"b", "c"},
						Tests: AggregateTest{
							"foo": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "C"}, {3, "D"}},
								Runtimes: []RuntimeSummary{{10, 20}, {30, 40}},
							},
						},
						FailureMap: map[string]string{},
						FailuresByType: map[string][]int{
							"AUDIO":   {80, 90},
							"CRASH":   {110, 220},
							"FAILURE": {42},
							"LEAKY":   {2},
						},
					},
				}
				expected := &AggregateResult{
					Version: ResultsVersion,
					Builder: "foo_builder",
					BuilderInfo: &BuilderInfo{
						SecondsEpoch: []float64{10, 20, 1, 2},
						BlinkRevs:    []Number{30, 40, 3, 4},
						BuildNumbers: []Number{50, 60, 5, 6},
						ChromeRevs:   []string{"b", "c", "a", "1"},
						Tests: AggregateTest{
							"foo": &AggregateTestLeaf{
								Results:  []ResultSummary{{3, "D"}, {1, "C"}, {1, "A"}, {3, "B"}},
								Runtimes: []RuntimeSummary{{30, 40}, {10, 20}, {1, 2}, {3, 4}},
							},
						},
						FailureMap: FailureLongNames,
						FailuresByType: map[string][]int{
							"AUDIO":   {80, 90, 1, 2, 3, 4},
							"CRASH":   {110, 220, 100, 200},
							"FAILURE": {42},
							"PASS":    {5},
							"LEAKY":   {2, 0},
						},
					},
				}
				So(ag.Merge(x), ShouldBeNil)
				So(ag, ShouldResemble, expected)
			})
		})
	})
}

// TestMergeAndTrim tests are ported from "model/test/jsonresults_test.py"
// in the Python implementation.
func TestMergeAndTrim(t *testing.T) {
	t.Parallel()

	Convey("Test Merge/Trim", t, func() {
		Convey("empty aggregated results", func() {
			aggr := &AggregateResult{}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("duplicate build number", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{100, "F"}},
							Runtimes: []RuntimeSummary{{100, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldEqual, ErrBuildNumberConflict)
		})

		Convey("incremental single test single run same result", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{201, "F"}},
							Runtimes: []RuntimeSummary{{201, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("single test single run different result", func() {
			aggr := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}, {200, "F"}},
							Runtimes: []RuntimeSummary{{1, 1}, {200, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("single test single run, result changed", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}, {10, "I"}},
							Runtimes: []RuntimeSummary{{200, 0}, {10, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}, {200, "F"}, {10, "I"}},
							Runtimes: []RuntimeSummary{{1, 1}, {200, 0}, {10, 1}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("multiple tests single run", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{100, "I"}},
							Runtimes: []RuntimeSummary{{100, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{201, "F"}},
							Runtimes: []RuntimeSummary{{201, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{101, "I"}},
							Runtimes: []RuntimeSummary{{101, 1}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("multiple tests single run no result", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{100, "I"}},
							Runtimes: []RuntimeSummary{{100, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "N"}, {200, "F"}},
							Runtimes: []RuntimeSummary{{201, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{101, "I"}},
							Runtimes: []RuntimeSummary{{101, 1}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("single test multiple runs", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{4, 3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{2, "I"}, {1, "Q"}},
							Runtimes: []RuntimeSummary{{3, 2}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{4, 3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "Q"}, {2, "I"}, {200, "F"}},
							Runtimes: []RuntimeSummary{{3, 2}, {200, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("multiple tests multiple runs", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "Z"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{4, 3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{2, "I"}},
							Runtimes: []RuntimeSummary{{2, 2}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "C"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{4, 3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{2, "I"}, {200, "F"}},
							Runtimes: []RuntimeSummary{{2, 2}, {200, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "C"}, {10, "Z"}},
							Runtimes: []RuntimeSummary{{1, 1}, {10, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("incremental result older build", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{5, "F"}},
							Runtimes: []RuntimeSummary{{5, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{2, 3, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{6, "F"}},
							Runtimes: []RuntimeSummary{{6, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("incremental result same build", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{5, "F"}},
							Runtimes: []RuntimeSummary{{5, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3, 2},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{2, "F"}},
							Runtimes: []RuntimeSummary{{2, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{7, "F"}},
							Runtimes: []RuntimeSummary{{7, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("remove new test", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{199, "F"}},
							Runtimes: []RuntimeSummary{{199, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"notrun.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "Y"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "N"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(200), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("remove test", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"directory": AggregateTest{
							"directory": AggregateTest{
								"001.html": &AggregateTestLeaf{
									Results:  []ResultSummary{{200, "P"}},
									Runtimes: []RuntimeSummary{{200, 0}},
								},
							},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "F"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{190, "P"}, {9, "N"}, {1, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"directory": AggregateTest{
							"directory": AggregateTest{
								"001.html": &AggregateTestLeaf{
									Results:  []ResultSummary{{1, "P"}},
									Runtimes: []RuntimeSummary{{1, 0}},
								},
							},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}, {10, "F"}},
							Runtimes: []RuntimeSummary{{11, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(200), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("updates expected", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"directory": AggregateTest{
							"directory": AggregateTest{
								"001.html": &AggregateTestLeaf{
									Expected: []string{"FAIL"},
									Results:  []ResultSummary{{200, "P"}},
									Runtimes: []RuntimeSummary{{200, 0}},
								},
							},
						},
						"002.html": &AggregateTestLeaf{
							Bugs:     []string{"crbug.com/1234"},
							Expected: []string{"FAIL"},
							Results:  []ResultSummary{{10, "F"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Expected: []string{"FAIL"},
							Results:  []ResultSummary{{190, "P"}, {9, "N"}, {1, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
						"004.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{199, "P"}, {1, "F"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"002.html": &AggregateTestLeaf{
							Expected: []string{"PASS"},
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Expected: []string{"TIMEOUT"},
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"004.html": &AggregateTestLeaf{
							Bugs:     []string{"crbug.com/1234"},
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}, {10, "F"}},
							Runtimes: []RuntimeSummary{{11, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Expected: []string{"TIMEOUT"},
							Results:  []ResultSummary{{191, "P"}, {9, "N"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
						"004.html": &AggregateTestLeaf{
							Bugs:     []string{"crbug.com/1234"},
							Results:  []ResultSummary{{200, "P"}},
							Runtimes: []RuntimeSummary{{200, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(200), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("keep test with all pass but slow time", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "P"}},
							Runtimes: []RuntimeSummary{{200, runtimeThresholdNormal}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "F"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{201, "P"}},
							Runtimes: []RuntimeSummary{{1, 1}, {200, runtimeThresholdNormal}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}, {10, "F"}},
							Runtimes: []RuntimeSummary{{11, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("pruning slow tests for debug builders", func() {
			aggr := &AggregateResult{
				Builder: "MockBuilder(dbg)",
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{200, "P"}},
							Runtimes: []RuntimeSummary{{200, runtimeThresholdDebug}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "F"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				Builder: "MockBuilder(dbg)",
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"003.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}},
							Runtimes: []RuntimeSummary{{1, 3}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				Builder: "MockBuilder(dbg)",
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{201, "P"}},
							Runtimes: []RuntimeSummary{{1, 1}, {200, runtimeThresholdDebug}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "P"}, {10, "F"}},
							Runtimes: []RuntimeSummary{{11, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(ResultsSize), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("prune extra results", func() {
			size := ResultsSize
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{size, "F"}, {1, "I"}},
							Runtimes: []RuntimeSummary{{size, 0}, {1, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "T"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "T"}, {size, "F"}},
							Runtimes: []RuntimeSummary{{1, 1}, {size, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(size), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("prune extra results small", func() {
			size := ResultsSmallSize
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{size, "F"}, {1, "I"}},
							Runtimes: []RuntimeSummary{{size, 0}, {1, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "T"}},
							Runtimes: []RuntimeSummary{{1, 1}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "T"}, {size, "F"}},
							Runtimes: []RuntimeSummary{{1, 1}, {size, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(size), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("prune extra results with new results of same type", func() {
			size := ResultsSmallSize
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{size, "F"}, {1, "N"}},
							Runtimes: []RuntimeSummary{{size, 0}, {1, 1}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{size, "F"}},
							Runtimes: []RuntimeSummary{{size, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr.Trim(size), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("merge build directory hierarchy", func() {
			aggr := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"bar": AggregateTest{
							"baz": AggregateTest{
								"003.html": &AggregateTestLeaf{
									Results:  []ResultSummary{{25, "F"}},
									Runtimes: []RuntimeSummary{{25, 0}},
								},
							},
						},
						"foo": AggregateTest{
							"001.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{50, "F"}},
								Runtimes: []RuntimeSummary{{50, 0}},
							},
							"002.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{100, "I"}},
								Runtimes: []RuntimeSummary{{100, 0}},
							},
						},
					},
				},
			}
			x := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"baz": AggregateTest{
							"004.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "I"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
						},
						"foo": AggregateTest{
							"001.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "F"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"002.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "I"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"bar": AggregateTest{
							"baz": AggregateTest{
								"003.html": &AggregateTestLeaf{
									Results:  []ResultSummary{{1, "N"}, {25, "F"}},
									Runtimes: []RuntimeSummary{{26, 0}},
								},
							},
						},
						"baz": AggregateTest{
							"004.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "I"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
						},
						"foo": AggregateTest{
							"001.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{51, "F"}},
								Runtimes: []RuntimeSummary{{51, 0}},
							},
							"002.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{101, "I"}},
								Runtimes: []RuntimeSummary{{101, 0}},
							},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("treats multiple results as a unique type", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{5, "F"}},
							Runtimes: []RuntimeSummary{{5, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{3, "FQ"}},
							Runtimes: []RuntimeSummary{{3, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "FIQ"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "FQ"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{2, 3, 1},
					Tests: AggregateTest{
						"001.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "FIQ"}, {5, "F"}},
							Runtimes: []RuntimeSummary{{6, 0}},
						},
						"002.html": &AggregateTestLeaf{
							Results:  []ResultSummary{{4, "FQ"}},
							Runtimes: []RuntimeSummary{{4, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})

		Convey("gtest", func() {
			aggr := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{2, 1},
					Tests: AggregateTest{
						"foo.bar": &AggregateTestLeaf{
							Results:  []ResultSummary{{50, "F"}},
							Runtimes: []RuntimeSummary{{50, 0}},
						},
						"foo.bar2": &AggregateTestLeaf{
							Results:  []ResultSummary{{100, "I"}},
							Runtimes: []RuntimeSummary{{100, 0}},
						},
						"test.failed": &AggregateTestLeaf{
							Results:  []ResultSummary{{5, "Q"}},
							Runtimes: []RuntimeSummary{{5, 0}},
						},
					},
				},
			}
			x := &AggregateResult{
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					Tests: AggregateTest{
						"foo.bar2": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "I"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"foo.bar3": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"test.failed": &AggregateTestLeaf{
							Results:  []ResultSummary{{5, "Q"}},
							Runtimes: []RuntimeSummary{{5, 0}},
						},
					},
				},
			}
			expected := &AggregateResult{
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					FailureMap:   FailureLongNames,
					BuildNumbers: []Number{3, 2, 1},
					Tests: AggregateTest{
						"foo.bar": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "N"}, {50, "F"}},
							Runtimes: []RuntimeSummary{{51, 0}},
						},
						"foo.bar2": &AggregateTestLeaf{
							Results:  []ResultSummary{{101, "I"}},
							Runtimes: []RuntimeSummary{{101, 0}},
						},
						"foo.bar3": &AggregateTestLeaf{
							Results:  []ResultSummary{{1, "F"}},
							Runtimes: []RuntimeSummary{{1, 0}},
						},
						"test.failed": &AggregateTestLeaf{
							Results:  []ResultSummary{{10, "Q"}},
							Runtimes: []RuntimeSummary{{10, 0}},
						},
					},
				},
			}
			So(aggr.Merge(x), ShouldBeNil)
			So(aggr, ShouldResemble, expected)
		})
	})
}
