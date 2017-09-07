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

func makeFakeAnalyzer(data []messages.ReasonRaw, errs []error) Analyzer {
	return func(context.Context, []*messages.BuildStep) ([]messages.ReasonRaw, []error) {
		return data, errs
	}
}

func TestReasonsForFailures(t *testing.T) {
	ctx := context.Background()
	Convey("ReasonsForFailure", t, func() {
		Convey("one analyzer", func() {
			Convey("nil", func() {
				analyzers = []Analyzer{makeFakeAnalyzer(nil, nil)}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil}), ShouldResemble, []messages.ReasonRaw{
					nil,
				})
			})

			Convey("not nil", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
				})
			})

			Convey("some nil", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						nil,
					}, nil),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})

			Convey("some errors", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						nil,
					}, []error{
						nil,
						errors.New("test err"),
					}),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})

			Convey("errors hide reasons", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
						&basicFailure{Name: "bar"},
					}, []error{
						nil,
						errors.New("test err"),
					}),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil, nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
					nil,
				})
			})
		})
		Convey("two analyzer", func() {
			Convey("both not nil", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "baz"},
					}, nil),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "baz"},
				})
			})

			Convey("both not nil, second errors", func() {
				analyzers = []Analyzer{
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "foo"},
					}, nil),
					makeFakeAnalyzer([]messages.ReasonRaw{
						&basicFailure{Name: "baz"},
					}, []error{
						errors.New("bad thing"),
					}),
				}

				So(ReasonsForFailures(ctx, []*messages.BuildStep{nil}), ShouldResemble, []messages.ReasonRaw{
					&basicFailure{Name: "foo"},
				})
			})
		})
	})
}

func TestBasicAnalyzer(t *testing.T) {
	Convey("basicAnalyzer", t, func() {
		Convey("basic", func() {
			reasons, err := basicAnalyzer(nil, []*messages.BuildStep{
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
			})
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
