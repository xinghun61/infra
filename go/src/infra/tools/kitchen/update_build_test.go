// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"testing"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"

	"go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/proto/milo"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestBuildUpdater(t *testing.T) {
	t.Parallel()

	Convey(`BuildUpdater`, t, func(c C) {
		ctx := context.Background()

		run := func(err1, err2 error) error {
			ctrl := gomock.NewController(t)
			defer ctrl.Finish()
			client := buildbucketpb.NewMockBuildsClient(ctrl)

			// req1 and req2 must be deep-different, so that gomock does not confuse
			// them.
			req1 := &buildbucketpb.UpdateBuildRequest{
				Build: &buildbucketpb.Build{
					Output: &buildbucketpb.Build_Output{
						SummaryMarkdown: "from req1",
					},
				},
			}
			req2 := &buildbucketpb.UpdateBuildRequest{
				Build: &buildbucketpb.Build{
					Output: &buildbucketpb.Build_Output{
						SummaryMarkdown: "from req2",
					},
				},
			}
			res := &buildbucketpb.Build{}
			gomock.InOrder(
				// non-last might be not called
				client.EXPECT().UpdateBuild(ctx, req1).MinTimes(0).Return(res, err1),
				// last one must be called exactly once
				client.EXPECT().UpdateBuild(ctx, req2).Times(1).Return(res, err2),
			)

			requests := make(chan *buildbucketpb.UpdateBuildRequest)
			done := make(chan error)
			go func() {
				done <- runBuildUpdater(ctx, client, requests)
			}()

			requests <- req1
			requests <- req2
			close(requests)
			return <-done
		}

		Convey("two successful requests", func() {
			So(run(nil, nil), ShouldBeNil)
		})

		Convey("first failed, second succeeded", func() {
			So(run(fmt.Errorf("transient"), nil), ShouldBeNil)
		})

		Convey("first succeeded, second failed", func() {
			So(run(nil, fmt.Errorf("fatal")), ShouldErrLike, "fatal")
		})
	})
}

func TestParseUpdateBuildRequest(t *testing.T) {
	t.Parallel()

	Convey(`parseUpdateBuildRequest`, t, func() {
		ctx := context.Background()

		ann := &milo.Step{}
		err := proto.UnmarshalText(`
			substep {
				step {
					name: "s1"
					property {
						name: "p1"
						value: "1"
					}
				}
			}
			substep {
				step {
					name: "s2"
					property {
						name: "p1"
						value: "11"
					}
					property {
						name: "p2"
						value: "2"
					}
				}
			}`, ann)
		expected := &buildbucketpb.UpdateBuildRequest{}
		err = proto.UnmarshalText(`
			build {
				steps {
					name: "s1"
					status: STARTED
				}
				steps {
					name: "s2"
					status: STARTED
				}
				output {
					properties {
						fields {
							key: "p1"
							value { number_value: 11 }
						}
						fields {
							key: "p2"
							value { number_value: 2 }
						}
					}
				}
			}
			update_mask {
				paths: "steps"
				paths: "output.properties"
			}
			fields {}
			`, expected)
		So(err, ShouldBeNil)

		annURL := "logdog://logdog.example.com/chromium/prefix/+/annotations"
		actual, err := parseUpdateBuildRequest(ctx, ann, annURL)
		So(err, ShouldBeNil)

		So(actual, ShouldResembleProto, expected)
	})
}
