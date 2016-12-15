// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"net/url"
	"testing"

	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDeviceAnalyzer(t *testing.T) {
	makeSteps := func(steps []messages.Step) []*messages.BuildStep {
		failures := []*messages.BuildStep{}
		for _, s := range steps {
			s := s
			failures = append(failures, &messages.BuildStep{
				Master: &messages.MasterLocation{URL: url.URL{
					Scheme: "https",
					Host:   "build.chromium.org",
					Path:   "/p/fake.Master",
				}},
				Build: &messages.Build{
					BuilderName: "fake_builder",
					Steps:       steps,
				},
				Step: &s,
			})
		}

		return failures
	}

	noFailure := []interface{}{
		messages.ResultOK,
	}
	stepFailure := []interface{}{
		messages.ResultOK + 1,
	}
	infraFailure := []interface{}{
		messages.ResultInfraFailure,
	}

	Convey("test analyze", t, func() {
		Convey("no failures", func() {
			reasons, err := deviceAnalyzer(nil, makeSteps([]messages.Step{}))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{})
		})

		Convey("empty", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
			})
		})

		Convey("perf step, no device affinity", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"some random",
						"text",
					},
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				nil,
			})
		})

		Convey("perf step, device affinity", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
			})
		})

		Convey("multiple perf steps", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 2",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 3",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
			})
		})

		Convey("multiple perf steps, Host Info", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name:    "Host Info",
					Results: infraFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 2",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 3",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
			})
		})

		Convey("multiple perf steps actually fail, Host Info", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name:    "Host Info",
					Results: infraFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: stepFailure,
				},
				{
					Name: "perf step 2",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: stepFailure,
				},
				{
					Name: "perf step 3",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: stepFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
			})
		})

		Convey("one device dead, one test fails", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: infraFailure,
				},
				{
					Name: "ok test",
					Text: []string{
						"<br>Device Affinity: 3",
					},
					Results: noFailure,
				},
				{
					Name: "failed test",
					Text: []string{
						"<br>Device Affinity: 3",
					},
					Results: stepFailure,
				},
				{
					Name: "perf step",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 2",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 3",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
			}

			reasons, err := deviceAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			// only 5 reasons, because ok_test passed.
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				nil,
				nil,
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
				&deviceFailure{
					Builder: "fake_builder",
					Devices: []int{4},
				},
			})
		})
	})
}

func TestPerfDeviceFailure(t *testing.T) {
	Convey("test", t, func() {
		Convey("devicesStr", func() {
			p := &deviceFailure{
				Devices: []int{1},
			}
			Convey("one device", func() {
				So(p.devicesStr(), ShouldEqual, "1")
			})

			p.Devices = append(p.Devices, 2)

			Convey("multiple devices", func() {
				So(p.devicesStr(), ShouldEqual, "1, 2")
			})
		})
	})
}

func TestGetDeviceAffinity(t *testing.T) {
	Convey("test", t, func() {
		Convey("getDeviceAffinity", func() {
			step := &messages.Step{
				Text: []string{
					"hi",
				},
			}

			Convey("non perf step", func() {
				rec, _, err := getDeviceAffinity(step)
				So(err, ShouldBeNil)
				So(rec, ShouldBeFalse)
			})

			Convey("perf step", func() {
				step.Text = []string{
					"Device Affinity: 1",
				}
				rec, num, err := getDeviceAffinity(step)
				So(err, ShouldBeNil)
				So(rec, ShouldBeTrue)
				So(num, ShouldEqual, 1)

				Convey("with br", func() {
					// Copied from buildbot logs
					step.Text = []string{
						"smoothness.key_silk_cases.reference<br>smoothness.key_silk_cases.reference<br><div class=\"BuildResultInfo\"><br></div><br><br/>Device Affinity: 4<br/>",
					}
					rec, num, err := getDeviceAffinity(step)
					So(err, ShouldBeNil)
					So(rec, ShouldBeTrue)
					So(num, ShouldEqual, 4)
				})
			})
		})
	})
}
