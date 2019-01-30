// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"errors"
	"testing"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

type fakeBuildStepAnalyzer struct {
	data []messages.ReasonRaw
	errs []error
}

func (f fakeBuildStepAnalyzer) Analyze(ctx context.Context, steps []*messages.BuildStep, tree string) ([]messages.ReasonRaw, []error) {
	return f.data, f.errs
}

func makeFakeBuildStepAnalyzer(data []messages.ReasonRaw, errs []error) BuildStepAnalyzer {
	return &fakeBuildStepAnalyzer{data, errs}
}

func TestReasonsForFailures(t *testing.T) {
	ctx := context.Background()
	Convey("ReasonsForFailure", t, func() {
		Convey("one analyzer", func() {
			Convey("nil", func() {
				analyzers := BuildStepAnalyzers{makeFakeBuildStepAnalyzer(nil, nil)}
				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil}, ""), ShouldResemble, []messages.ReasonRaw{
					nil,
				})
			})

			Convey("not nil", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
				})
			})

			Convey("some nil", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						nil,
					}, nil),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})

			Convey("some errors", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						nil,
					}, []error{
						nil,
						errors.New("test err"),
					}),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})

			Convey("errors hide reasons", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						&basicFailure{Name: "bar"},
					}, []error{
						nil,
						errors.New("test err"),
					}),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})
		})

		Convey("two analyzer", func() {
			Convey("both not nil", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "baz"},
					}, nil),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "baz"},
				})
			})

			Convey("both not nil, second errors", func() {
				analyzers := BuildStepAnalyzers{
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
					makeFakeBuildStepAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "baz"},
					}, []error{
						errors.New("bad thing"),
					}),
				}

				So(analyzers.ReasonsForFailures(ctx, []*messages.BuildStep{nil}, ""), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
				})
			})
		})
	})
}

func TestBasicStepAnalyzer(t *testing.T) {
	Convey("basicStepAnalyzer", t, func() {
		Convey("basic", func() {
			ba := &basicStepAnalyzer{}
			reasons, err := ba.Analyze(nil, []*messages.BuildStep{
				{
					Step: &messages.Step{
						Name: "foo",
					},
				},
				{
					Step: &messages.Step{
						Name: "bar",
					},
				},
			}, "")
			So(err, ShouldBeNil)
			So(reasons, ShouldResemble, []messages.ReasonRaw{
				&basicFailure{
					Name: "foo",
				},
				&basicFailure{
					Name: "bar",
				},
			})
		})

	})
}
