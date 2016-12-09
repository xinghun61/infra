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

func TestEndToEnd(t *testing.T) {
	t.Parallel()

	Convey("End to end", t, func() {
		// This test is a port of the test named "test_merge_full_results_format"
		// from "model/test/jsonresults_test.py" in the Python
		// application.
		Convey("FullResult: clean, unmarshal JSON, merge, trim", func() {
			b, err := ioutil.ReadFile(filepath.Join("testdata", "full_results.jsonp"))
			So(err, ShouldBeNil)
			r, err := CleanJSON(bytes.NewReader(bytes.TrimSpace(b)))
			So(err, ShouldBeNil)

			expected := &AggregateResult{
				Builder: "Webkit",
				Version: ResultsVersion,
				BuilderInfo: &BuilderInfo{
					BuildNumbers: []Number{3},
					ChromeRevs:   []string{"5678"},
					FailureMap:   FailureLongNames,
					FailuresByType: map[string][]int{
						"AUDIO":      {0},
						"CRASH":      {3},
						"FAIL":       {2},
						"IMAGE":      {1},
						"IMAGE+TEXT": {0},
						"MISSING":    {0},
						"PASS":       {10},
						"SKIP":       {2},
						"TEXT":       {3},
						"TIMEOUT":    {16},
						"LEAK":       {1},
					},
					SecondsEpoch: []float64{1368146629},
					Tests: AggregateTest{
						"media": AggregateTest{
							"W3C": AggregateTest{
								"audio": AggregateTest{
									"src": AggregateTest{
										"src_removal_does_not_trigger_loadstart.html": &AggregateTestLeaf{
											Results:  []ResultSummary{{1, "P"}},
											Runtimes: []RuntimeSummary{{1, 4}},
										},
									},
								},
								// "video" is not present because the
								// expected fields are "PASS" and "NOTRUN".
							},
							"encrypted-media": AggregateTest{
								"random-test-1.html": &AggregateTestLeaf{
									Bugs:     []string{"crbug.com/1234"},
									Results:  []ResultSummary{{1, "T"}},
									Runtimes: []RuntimeSummary{{1, 6}},
									Expected: []string{"TIMEOUT"},
								},
								"random-test-2.html": &AggregateTestLeaf{
									Expected: []string{"TIMEOUT"},
									Results:  []ResultSummary{{1, "T"}},
									Runtimes: []RuntimeSummary{{1, 0}},
								},
							},
							"media-document-audio-repaint.html": &AggregateTestLeaf{
								Expected: []string{"IMAGE"},
								Results:  []ResultSummary{{1, "I"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"progress-events-generated-correctly.html": &AggregateTestLeaf{
								Expected: []string{"PASS", "FAIL", "IMAGE", "TIMEOUT", "CRASH", "MISSING"},
								Results:  []ResultSummary{{1, "T"}},
								Runtimes: []RuntimeSummary{{1, 6}},
							},
							"flaky-failed.html": &AggregateTestLeaf{
								Expected: []string{"PASS", "FAIL"},
								Results:  []ResultSummary{{1, "Q"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"unexpected-fail.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "Q"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"unexpected-leak.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "K"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"unexpected-flake.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "QP"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
							"unexpected-unexpected.html": &AggregateTestLeaf{
								Results:  []ResultSummary{{1, "U"}},
								Runtimes: []RuntimeSummary{{1, 0}},
							},
						},
					},
				},
			}

			var aggr AggregateResult
			aggr.Builder = "Webkit"
			var result FullResult

			So(json.NewDecoder(r).Decode(&result), ShouldBeNil)
			convertedAggr, err := result.AggregateResult()
			So(err, ShouldBeNil)
			So(aggr.Merge(&convertedAggr), ShouldBeNil)
			So(aggr.Trim(ResultsSize), ShouldBeNil)
			So(&aggr, ShouldResemble, expected)
		})
	})
}
