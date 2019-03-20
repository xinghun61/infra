// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"go.chromium.org/luci/buildbucket"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/logdog/common/types"
	"go.chromium.org/luci/lucictx"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func newAnn(stepNames ...string) *milo.Step {
	ann := &milo.Step{
		Substep: make([]*milo.Step_Substep, len(stepNames)),
	}
	for i, n := range stepNames {
		ann.Substep[i] = &milo.Step_Substep{
			Substep: &milo.Step_Substep_Step{
				Step: &milo.Step{Name: n},
			},
		}
	}
	return ann
}

func newAnnBytes(stepNames ...string) []byte {
	ret, err := proto.Marshal(newAnn(stepNames...))
	if err != nil {
		panic(err)
	}
	return ret
}

func TestBuildUpdater(t *testing.T) {
	t.Parallel()

	Convey(`buildUpdater`, t, func(c C) {
		ctrl := gomock.NewController(t)
		defer ctrl.Finish()
		client := buildbucketpb.NewMockBuildsClient(ctrl)

		// Ensure tests don't hang.
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)

		ctx, clk := testclock.UseTime(ctx, testclock.TestRecentTimeUTC)

		bu := &buildUpdater{
			buildID:    42,
			buildToken: "build token",
			annAddr: &types.StreamAddr{
				Host:    "logdog.example.com",
				Project: "chromium",
				Path:    "prefix/+/annotations",
			},
			client:      client,
			annotations: make(chan []byte),
		}

		Convey("build token is sent", func() {
			updateBuild := func(ctx context.Context, req *buildbucketpb.UpdateBuildRequest) (*buildbucketpb.Build, error) {
				md, ok := metadata.FromOutgoingContext(ctx)
				c.So(ok, ShouldBeTrue)
				c.So(md.Get(buildbucket.BuildTokenHeader), ShouldResemble, []string{"build token"})
				res := &buildbucketpb.Build{}
				return res, nil
			}
			client.EXPECT().
				UpdateBuild(gomock.Any(), gomock.Any()).
				AnyTimes().
				DoAndReturn(updateBuild)

			err := bu.UpdateBuild(ctx, &buildbucketpb.UpdateBuildRequest{})
			So(err, ShouldBeNil)
		})

		Convey(`run`, func() {
			update := func(ctx context.Context, annBytes []byte) error {
				return nil
			}

			errC := make(chan error)
			done := make(chan struct{})
			start := func() {
				go func() {
					errC <- bu.run(ctx, done, update)
				}()
			}

			run := func(err1, err2 error) error {
				update = func(ctx context.Context, annBytes []byte) error {
					if string(annBytes) == "1" {
						return err1
					}
					return err2
				}
				start()
				bu.AnnotationUpdated([]byte("1"))
				bu.AnnotationUpdated([]byte("2"))
				cancel()
				return <-errC
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

			Convey("minDistance", func() {
				var sleepDuration time.Duration
				open := true
				clk.SetTimerCallback(func(d time.Duration, t clock.Timer) {
					if testclock.HasTags(t, "update-build-distance") {
						sleepDuration += d
						clk.Add(d)

						if open {
							close(done)
							open = false
						}

					}
				})

				start()
				bu.AnnotationUpdated([]byte("1"))
				So(<-errC, ShouldBeNil)
				So(sleepDuration, ShouldBeGreaterThanOrEqualTo, time.Second)
			})

			Convey("errSleep", func() {
				attempt := 0
				clk.SetTimerCallback(func(d time.Duration, t clock.Timer) {
					switch {
					case testclock.HasTags(t, "update-build-distance"):
						clk.Add(d)
					case testclock.HasTags(t, "update-build-error"):
						clk.Add(d)
						attempt++
						if attempt == 4 {
							bu.AnnotationUpdated([]byte("2"))
						}
					}
				})

				update = func(ctx context.Context, annBytes []byte) error {
					if string(annBytes) == "1" {
						return fmt.Errorf("err")
					}

					close(done)
					return nil
				}

				start()
				bu.AnnotationUpdated([]byte("1"))
				So(<-errC, ShouldBeNil)
			})

			Convey("first is fatal, second never occurs", func() {
				fatal := status.Error(codes.InvalidArgument, "too large")
				calls := 0
				update = func(ctx context.Context, annBytes []byte) error {
					calls++
					return fatal
				}
				start()
				bu.AnnotationUpdated([]byte("1"))
				cancel()
				So(errors.Unwrap(<-errC), ShouldEqual, fatal)
				So(calls, ShouldEqual, 1)
			})

			Convey("done is closed", func() {
				start()
				bu.AnnotationUpdated([]byte("1"))
				close(done)
				So(<-errC, ShouldBeNil)
			})
		})
	})

}

func TestReadBuildSecrets(t *testing.T) {
	t.Parallel()

	Convey("readBuildSecrets", t, func() {
		ctx := context.Background()
		ctx = lucictx.SetSwarming(ctx, nil)

		Convey("empty", func() {
			secrets, err := readBuildSecrets(ctx)
			So(err, ShouldBeNil)
			So(secrets, ShouldBeNil)
		})

		Convey("build token", func() {
			secretBytes, err := proto.Marshal(&buildbucketpb.BuildSecrets{
				BuildToken: "build token",
			})
			So(err, ShouldBeNil)

			ctx = lucictx.SetSwarming(ctx, &lucictx.Swarming{SecretBytes: secretBytes})

			secrets, err := readBuildSecrets(ctx)
			So(err, ShouldBeNil)
			So(string(secrets.BuildToken), ShouldEqual, "build token")
		})
	})
}
