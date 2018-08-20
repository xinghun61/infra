// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"testing"

	ds "go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestWorkerLaunchedRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		// Add pending workflow run entity.
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		workflowRun := &track.WorkflowRun{ID: 1, Parent: requestKey}
		So(ds.Put(ctx, workflowRun), ShouldBeNil)
		workflowRunKey := ds.KeyForObj(ctx, workflowRun)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			ID:     1,
			Parent: workflowRunKey,
			State:  tricium.State_PENDING,
		}), ShouldBeNil)

		// Mark workflow as launched and add tracking entities for workers.
		err := workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
			RunId: request.ID,
		}, mockWorkflowProvider{})
		So(err, ShouldBeNil)

		// Mark worker as launched.
		err = workerLaunched(ctx, &admin.WorkerLaunchedRequest{
			RunId:  request.ID,
			Worker: fileIsolator,
		})
		So(err, ShouldBeNil)

		Convey("Marks worker as launched", func() {
			functionName, _, err := track.ExtractFunctionPlatform(fileIsolator)
			So(err, ShouldBeNil)
			functionRunKey := ds.NewKey(ctx, "FunctionRun", functionName, 0, workflowRunKey)
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolator, 0, functionRunKey)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			err = ds.Get(ctx, wr)
			So(err, ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_RUNNING)
			fr := &track.FunctionRunResult{ID: 1, Parent: functionRunKey}
			err = ds.Get(ctx, fr)
			So(err, ShouldBeNil)
			So(fr.State, ShouldEqual, tricium.State_RUNNING)
		})

		Convey("Validates request", func() {
			// Validate run id.
			s := &trackerServer{}
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{})
			So(err.Error(), ShouldEqual, "rpc error: code = InvalidArgument desc = missing run ID")

			// Validate worker.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId: request.ID,
			})
			So(err.Error(), ShouldEqual, "rpc error: code = InvalidArgument desc = missing worker")

			// Validate input hash.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId:  request.ID,
				Worker: fileIsolator,
			})
			So(err.Error(), ShouldEqual, "rpc error: code = InvalidArgument desc = missing isolated input hash")

			// Validate swarming and buildbucket missing.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId:             request.ID,
				Worker:            fileIsolator,
				IsolatedInputHash: "hash",
			})
			So(err.Error(), ShouldEqual, "rpc error: code = InvalidArgument desc = missing swarming task and buildbucket ID, one must be present")

			// Validate both swarming and buildbucket present.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId:              request.ID,
				Worker:             fileIsolator,
				IsolatedInputHash:  "hash",
				SwarmingTaskId:     "id",
				BuildbucketBuildId: 12,
			})
			So(err.Error(), ShouldEqual, "rpc error: code = InvalidArgument desc = have both swarming and buildbucket IDs, only one can be present")

			// Validate swarming.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId:             request.ID,
				Worker:            fileIsolator,
				IsolatedInputHash: "hash",
				SwarmingTaskId:    "id",
			})
			So(err, ShouldBeNil)

			// Validate buildbucket.
			_, err = s.WorkerLaunched(ctx, &admin.WorkerLaunchedRequest{
				RunId:              request.ID,
				Worker:             fileIsolator,
				IsolatedInputHash:  "hash",
				BuildbucketBuildId: 12,
			})
			So(err, ShouldBeNil)
		})
	})
}
