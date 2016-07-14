package model

import (
	"encoding/json"
	"io/ioutil"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestResults(t *testing.T) {
	t.Parallel()

	Convey("TestResults", t, func() {
		Convey("Unmarshal", func() {
			Convey("Unit tests", func() {
				tm := map[string]interface{}{
					"version": 4,
					"foo_builder": map[string]interface{}{
						"blinkRevision":     []string{"100", "200", "0", "-50"},
						"secondsSinceEpoch": []int{40 << 20, 4 << 20, 400 << 2, -42},
						"chromeRevision":    []string{"10", "40", "900", "65536"},
						"buildNumbers":      []string{"9000", "7500", "-42", "0"},
						"failure_map":       map[string]string{"A": "Audio", "C": "Crash"},
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
				t := TestResults{Builder: "foo_builder"}

				Convey("Version", func() {
					Convey("Should returns error for invalid errors", func() {
						tm["version"] = 9000
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "version")

						tm["version"] = "a"
						b = marshal(tm)
						err = json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "version")
					})

					Convey("Should succeed for valid versions", func() {
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
					Convey("Should return error for wrong builder type", func() {
						tm["foo_builder"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "null")

						tm["foo_builder"] = []int{}
						b = marshal(tm)
						err = json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error for missing builder key", func() {
						delete(tm, "foo_builder")
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "missing builder")
					})

					Convey("Should succeed for valid builder", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.Builder, ShouldEqual, "foo_builder")
					})
				})

				Convey("secondsSinceEpoch", func() {
					Convey("Should return error for wrong secondsSinceEpoch element type", func() {
						tm["foo_builder"].(map[string]interface{})["secondsSinceEpoch"] =
							[]interface{}{1, 2, "a"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error for wrong secondsSinceEpoch list type", func() {
						tm["foo_builder"].(map[string]interface{})["secondsSinceEpoch"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "secondsSinceEpoch")
					})

					Convey("Should succeed for valid secondsSinceEpoch", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.SecondsSinceEpoch, ShouldResemble, tm["foo_builder"].(map[string]interface{})["secondsSinceEpoch"])
					})
				})

				Convey("blinkRevison", func() {
					Convey("Should return error for wrong blinkRevison element type", func() {
						tm["foo_builder"].(map[string]interface{})["blinkRevision"] = []interface{}{"900", "bad"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error for wrong blinkRevision list type", func() {
						tm["foo_builder"].(map[string]interface{})["blinkRevision"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "blinkRevision")
					})

					Convey("Should succeed for valid blinkRevision", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.BlinkRevision, ShouldResemble, []number{100, 200, 0, -50})
					})
				})

				Convey("buildNumbers", func() {
					Convey("Should return error for wrong buildNumbers element type", func() {
						tm["foo_builder"].(map[string]interface{})["buildNumbers"] = []interface{}{"900", "bad"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error for wrong buildNumbers list type", func() {
						tm["foo_builder"].(map[string]interface{})["buildNumbers"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "buildNumbers")
					})

					Convey("Should succeed for valid buildNumbers", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.BuildNumbers, ShouldResemble, []number{9000, 7500, -42, 0})
					})
				})

				Convey("chromeRevision", func() {
					Convey("Should return error for wrong chromeRevision element type", func() {
						tm["foo_builder"].(map[string]interface{})["chromeRevision"] = []interface{}{"900", "bad"}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error for wrong chromeRevision list type", func() {
						tm["foo_builder"].(map[string]interface{})["chromeRevision"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
						So(err.Error(), ShouldContainSubstring, "chromeRevision")
					})

					Convey("Should succeed for valid chromeRevision", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.ChromeRevision, ShouldResemble, []number{10, 40, 900, 65536})
					})
				})

				Convey("num_failures_by_type", func() {
					Convey("Should return error: num_failures_by_type exists, has wrong type, missing fixableCounts ", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = nil
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should return error: num_failures_by_type exists, has wrong inner type, missing fixableCounts", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] =
							map[string][]interface{}{"bar": {"baz"}}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should succeed: num_failures_by_type exists and is right type", func() {
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldBeNil)
						So(t.FailuresByType, ShouldResemble, tm["foo_builder"].(map[string]interface{})["num_failures_by_type"])
					})

					Convey("Should return error: num_failures_by_type is invalid, fixableCounts is invalid", func() {
						tm["foo_builder"].(map[string]interface{})["num_failures_by_type"] = nil
						tm["foo_builder"].(map[string]interface{})["fixableCounts"] = map[string]string{}
						b := marshal(tm)
						err := json.Unmarshal(b, &t)
						So(err, ShouldNotBeNil)
					})

					Convey("Should succeed: num_failures_by_type is invalid but fixableCounts is valid", func() {
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

				Convey("Should return error on absent builder", func() {
					t := TestResults{Builder: "non_existent_builder"}
					So(json.Unmarshal(good, &t), ShouldNotBeNil)
				})

				Convey("Existing builder", func() {
					t := TestResults{Builder: "win_chromium_rel_ng"}
					So(json.Unmarshal(good, &t), ShouldBeNil)

					Convey("Should have correct version", func() {
						So(t.Version, ShouldEqual, 4)
					})

					Convey("Marshal and Unmarshal should be inverse ops", func() {
						var (
							repeater = TestResults{Builder: "win_chromium_rel_ng"}
							s        = TestResults{Builder: "win_chromium_rel_ng"}
						)

						So(json.Unmarshal(good, &repeater), ShouldBeNil)
						b, err := json.Marshal(&repeater)
						So(err, ShouldBeNil)

						So(json.Unmarshal(b, &s), ShouldBeNil)
						So(s, ShouldResemble, t)
					})
				})
			})
		})
	})
}
