// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"fmt"
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
			reasons, err := botAnalyzer(nil, makeSteps([]messages.Step{}))

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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
			})
		})

		Convey("test failure, device affinity", func() {
			steps := []messages.Step{
				{
					Name:    "first",
					Results: stepFailure,
				},
				{
					Name: "perf stepppp",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: stepFailure,
				},
			}

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				nil,
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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
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

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
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
					Name: "perf step 99",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 2 99",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
				{
					Name: "perf step 3 99",
					Text: []string{
						"<br>Device Affinity: 4",
					},
					Results: infraFailure,
				},
			}

			reasons, err := botAnalyzer(nil, makeSteps(steps))

			So(err, ShouldBeNil)
			// only 5 reasons, because ok_test passed.
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				nil,
				nil,
				nil,
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
				&botFailure{
					Builder: "fake_builder",
					Bots:    []string{"4"},
				},
			})
		})
	})
}

func TestPerfDeviceFailure(t *testing.T) {
	Convey("test", t, func() {
		Convey("devicesStr", func() {
			p := &botFailure{
				Bots: []string{"1"},
			}
			Convey("one device", func() {
				So(p.devicesStr(), ShouldEqual, "1")
			})

			p.Bots = append(p.Bots, "2")

			Convey("multiple devices", func() {
				So(p.devicesStr(), ShouldEqual, "1, 2")
			})
		})
	})
}

func TestGetBotID(t *testing.T) {
	Convey("test", t, func() {
		Convey("getBotID", func() {
			step := &messages.Step{
				Text: []string{
					"hi",
				},
			}

			Convey("non perf step", func() {
				res := getBotID(step)
				So(res, ShouldEqual, "")
			})

			for title, prefix := range map[string]string{
				"perf android": "Device Affinity:",
				"perf desktop": "Bot id:",
			} {
				Convey(fmt.Sprintf("%s step", title), func() {
					step.Text = []string{
						fmt.Sprintf("%s foo", prefix),
					}
					res := getBotID(step)
					So(res, ShouldEqual, "foo")

					Convey("with br", func() {
						// Copied from buildbot logs
						step.Text = []string{
							fmt.Sprintf("smoothness.key_silk_cases.reference<br>smoothness.key_silk_cases.reference<br><div class=\"BuildResultInfo\"><br></div><br><br/>%s bar<br/>Other ignored junk", prefix),
							"some other junk that should be ignored",
						}
						res := getBotID(step)
						So(res, ShouldEqual, "bar")
					})
				})
			}
		})
	})
}
