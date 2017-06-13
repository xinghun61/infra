// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"testing"

	ds "github.com/luci/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestWorkerLaunchedRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		// Add pending workflow run entity.
		request := &track.AnalyzeRequest{}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		run := &track.WorkflowRun{ID: 1, Parent: requestKey}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			ID:     1,
			Parent: runKey,
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
			analyzerName, err := track.ExtractAnalyzerName(fileIsolator)
			So(err, ShouldBeNil)
			analyzerKey := ds.NewKey(ctx, "AnalyzerRun", analyzerName, 0, runKey)
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolator, 0, analyzerKey)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			err = ds.Get(ctx, wr)
			So(err, ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_RUNNING)
			ar := &track.AnalyzerRunResult{ID: 1, Parent: analyzerKey}
			err = ds.Get(ctx, ar)
			So(err, ShouldBeNil)
			So(ar.State, ShouldEqual, tricium.State_RUNNING)
		})
	})
}
