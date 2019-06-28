// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestResults(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		// Add request->run->analyzer->worker->comments.
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		So(ds.Put(ctx, &track.AnalyzeRequestResult{
			ID:     1,
			Parent: requestKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		run := &track.WorkflowRun{
			ID:     1,
			Parent: requestKey,
		}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			Parent: runKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		functionName := "Hello"
		platform := tricium.Platform_UBUNTU
		analyzerKey := ds.NewKey(ctx, "FunctionRun", functionName, 0, runKey)
		So(ds.Put(ctx, &track.FunctionRun{
			ID:     functionName,
			Parent: runKey,
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:     1,
			Parent: analyzerKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		workerName := functionName + "_UBUNTU"
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, analyzerKey)
		So(ds.Put(ctx, &track.WorkerRun{
			ID:       workerName,
			Parent:   analyzerKey,
			Platform: platform,
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.WorkerRunResult{
			ID:          1,
			Parent:      workerKey,
			State:       tricium.State_SUCCESS,
			NumComments: 1,
		}), ShouldBeNil)
		json, err := (&jsonpb.Marshaler{}).MarshalToString(&tricium.Data_Comment{
			Category: functionName,
			Message:  "Hello",
		})
		So(err, ShouldBeNil)
		comment := &track.Comment{
			Parent:    workerKey,
			Category:  functionName,
			Comment:   []byte(json),
			Platforms: 0,
		}
		So(ds.Put(ctx, comment), ShouldBeNil)
		commentKey := ds.KeyForObj(ctx, comment)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   commentKey,
			Included: true,
		}), ShouldBeNil)
		comment = &track.Comment{
			Parent:    workerKey,
			Category:  functionName,
			Comment:   []byte(json),
			Platforms: 0,
		}
		So(ds.Put(ctx, comment), ShouldBeNil)
		commentKey = ds.KeyForObj(ctx, comment)
		So(ds.Put(ctx, &track.CommentSelection{
			ID:       1,
			Parent:   commentKey,
			Included: false,
		}), ShouldBeNil)

		Convey("Merged results request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			results, isMerged, err := results(ctx, request.ID)
			So(err, ShouldBeNil)
			So(len(results.Comments), ShouldEqual, 1)
			So(isMerged, ShouldBeTrue)
			comment := results.Comments[0]
			So(comment.Category, ShouldEqual, functionName)
		})
	})
}
