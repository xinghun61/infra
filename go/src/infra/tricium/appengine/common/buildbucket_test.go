// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"testing"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/ptypes/struct"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/logging/memlogger"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

func TestTrigger(t *testing.T) {
	Convey("Triggers a build", t, func() {
		w := &admin.Worker{
			Name:       "FileIsolator",
			Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
			Deadline:   1200,
			Impl: &admin.Worker_Recipe{
				Recipe: &tricium.Recipe{
					Project: "tricium",
					Bucket:  "try",
					Builder: "analyzer",
				},
			},
		}
		params := &TriggerParameters{
			Worker:         w,
			PubsubUserdata: "data",
			Patch: PatchDetails{
				GerritHost:    "https://chromium-review.googlesource.com",
				GerritProject: "chromium/src",
				GerritChange:  "chromium~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
				GerritCl:      "12345",
				GerritPatch:   "2",
			},
		}
		ctx := memory.Use(memlogger.Use(context.Background()))
		ctrl := gomock.NewController(t)
		defer ctrl.Finish()
		client := buildbucketpb.NewMockBuildsClient(ctrl)

		scheduleBuild := func(ctx context.Context, req *buildbucketpb.ScheduleBuildRequest) (*buildbucketpb.Build, error) {
			res := &buildbucketpb.Build{Id: 1}
			return res, nil
		}
		client.EXPECT().
			ScheduleBuild(gomock.Any(), gomock.Any()).
			AnyTimes().
			DoAndReturn(scheduleBuild)

		result, err := trigger(ctx, params, client)
		So(err, ShouldBeNil)
		So(result.BuildID, ShouldEqual, 1)

	})
}

func TestCollect(t *testing.T) {
	Convey("Collects a build", t, func() {
		params := &CollectParameters{
			BuildID: 1,
		}
		ctx := memory.Use(memlogger.Use(context.Background()))
		ctrl := gomock.NewController(t)
		defer ctrl.Finish()
		client := buildbucketpb.NewMockBuildsClient(ctrl)

		getBuild := func(ctx context.Context, req *buildbucketpb.GetBuildRequest) (*buildbucketpb.Build, error) {
			res := &buildbucketpb.Build{
				Id:     1,
				Status: buildbucketpb.Status_SUCCESS,
				Output: &buildbucketpb.Build_Output{
					Properties: &structpb.Struct{
						Fields: map[string]*structpb.Value{
							"tricium": {
								Kind: &structpb.Value_StringValue{StringValue: "{\"tricium\": []}"},
							},
						}},
				},
			}
			return res, nil
		}
		client.EXPECT().
			GetBuild(gomock.Any(), gomock.Any()).
			AnyTimes().
			DoAndReturn(getBuild)

		result, err := collect(ctx, params, client)
		So(err, ShouldBeNil)
		So(result.State, ShouldEqual, Success)
		So(result.BuildbucketOutput, ShouldEqual, "{\"tricium\": []}")
	})
}
