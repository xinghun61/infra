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
	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	structpb "github.com/golang/protobuf/ptypes/struct"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"go.chromium.org/luci/buildbucket"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/logdog/common/types"
	"go.chromium.org/luci/lucictx"

	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	luciproto "go.chromium.org/luci/common/proto"

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

		Convey("ParseAnnotations", func() {
			ann := &milo.Step{}
			err := luciproto.UnmarshalTextML(`
				substep: <
					step: <
						name: "bot_update"
						status: SUCCESS
						started: < seconds: 1400000000 >
						ended: < seconds: 1400001000 >
						property: <
							name: "$recipe_engine/buildbucket/output_gitiles_commit"
							value: <<END
							{
								"host": "chrome-internal.googlesource.com",
								"project": "chromeos/manifest-internal",
								"ref": "refs/heads/master",
								"id": "91401dc270212d98734ab894bd90609b882aa458",
								"position": 2
							}
END
						>
					>
				>
				substep: <
					step: <
						name: "compile"
						status: RUNNING
						started: < seconds: 1400001000 >
						property: <
							name: "foo"
							value: "\"bar\""
						>
					>
				>
			`, ann)
			So(err, ShouldBeNil)
			So(ann.Substep, ShouldHaveLength, 2)

			expected := &buildbucketpb.UpdateBuildRequest{}
			err = jsonpb.UnmarshalString(`{
				"build": {
					"id": 42,
					"steps": [
						{
							"name": "bot_update",
							"status": "SUCCESS",
							"startTime": "2014-05-13T16:53:20.0Z",
							"endTime": "2014-05-13T17:10:00.0Z"

						},
						{
							"name": "compile",
							"status": "STARTED",
							"startTime": "2014-05-13T17:10:00.0Z"
						}
					],
					"output": {
						"properties": {"foo": "bar"},
						"gitilesCommit": {
							"host": "chrome-internal.googlesource.com",
							"project": "chromeos/manifest-internal",
							"ref": "refs/heads/master",
							"id": "91401dc270212d98734ab894bd90609b882aa458",
							"position": 2
						}
					}
				},
				"updateMask": {
					"paths": [
						"build.steps",
						"build.output.properties",
						"build.output.gitiles_commit"
					]
				}
			}`, expected)
			So(err, ShouldBeNil)

			actual, err := bu.ParseAnnotations(ctx, ann)
			So(err, ShouldBeNil)
			So(actual, ShouldResembleProto, expected)
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

func TestOutputCommitFromLegacyProperties(t *testing.T) {
	t.Parallel()

	parse := func(repository, gotRevision, gotRevisionCP string) (*buildbucketpb.GitilesCommit, error) {
		return outputCommitFromLegacyProperties(&structpb.Struct{
			Fields: map[string]*structpb.Value{
				"repository": {
					Kind: &structpb.Value_StringValue{StringValue: repository},
				},
				"got_revision": {
					Kind: &structpb.Value_StringValue{StringValue: gotRevision},
				},
				"got_revision_cp": {
					Kind: &structpb.Value_StringValue{StringValue: gotRevisionCP},
				},
			},
		})
	}

	Convey("TestOutputCommitFromLegacyProperties", t, func() {
		Convey("no properties", func() {
			actual, err := parse("", "", "")
			So(err, ShouldBeNil)
			So(actual, ShouldBeNil)
		})

		Convey("no repo", func() {
			actual, err := parse("", "e57f4e87022d765b45e741e478a8351d9789bc37", "")
			So(err, ShouldBeNil)
			So(actual, ShouldBeNil)
		})

		Convey("got_revision id", func() {
			actual, err := parse("https://chromium.googlesource.com/chromium/src", "e57f4e87022d765b45e741e478a8351d9789bc37", "")
			So(err, ShouldBeNil)
			So(actual, ShouldResembleProto, &buildbucketpb.GitilesCommit{
				Host:    "chromium.googlesource.com",
				Project: "chromium/src",
				Id:      "e57f4e87022d765b45e741e478a8351d9789bc37",
			})
		})

		Convey("got_revision ref", func() {
			actual, err := parse("https://chromium.googlesource.com/chromium/src", "refs/heads/master", "")
			So(err, ShouldBeNil)
			So(actual, ShouldResembleProto, &buildbucketpb.GitilesCommit{
				Host:    "chromium.googlesource.com",
				Project: "chromium/src",
				Ref:     "refs/heads/master",
			})
		})

		Convey("got_revision_cp", func() {
			actual, err := parse("https://chromium.googlesource.com/chromium/src", "e57f4e87022d765b45e741e478a8351d9789bc37", "refs/heads/master@{#673406}")
			So(err, ShouldBeNil)
			So(actual, ShouldResembleProto, &buildbucketpb.GitilesCommit{
				Host:     "chromium.googlesource.com",
				Project:  "chromium/src",
				Ref:      "refs/heads/master",
				Id:       "e57f4e87022d765b45e741e478a8351d9789bc37",
				Position: 673406,
			})
		})
	})
}
