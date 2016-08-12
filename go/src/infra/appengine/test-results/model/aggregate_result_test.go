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
		b := `[1,0.001]`

		Convey("Unmarshal", func() {
			Convey("Simple floats", func() {
				var actual RuntimeSummary
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
						"secondsSinceEpoch": []int64{40 << 20, 4 << 20, 400 << 2, -42},
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

				Convey("Absent builder", func() {
					t := AggregateResult{Builder: "non_existent_builder"}
					So(json.Unmarshal(good, &t), ShouldNotBeNil)
				})

				Convey("Existing builder", func() {
					t := AggregateResult{Builder: "win_chromium_rel_ng"}
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
			})
		})
	})
}
