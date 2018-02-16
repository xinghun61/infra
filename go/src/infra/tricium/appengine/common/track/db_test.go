// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	"testing"

	ds "go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"
	"infra/tricium/api/v1"

	trit "infra/tricium/appengine/common/testing"
)

func TestTrackHelperFunctions(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &trit.Testing{}
		ctx := tt.Context()
		var runID int64 = 123

		// Add completed request.
		request := &AnalyzeRequest{
			ID: runID,
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		So(ds.Put(ctx, &AnalyzeRequestResult{
			ID:     1,
			Parent: requestKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		functionName := "Hello"
		run := &WorkflowRun{
			ID:        1,
			Parent:    requestKey,
			Functions: []string{functionName},
		}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &WorkflowRunResult{
			ID:     1,
			Parent: runKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		platform := tricium.Platform_UBUNTU
		functionKey := ds.NewKey(ctx, "FunctionRun", functionName, 0, runKey)
		workerName := functionName + "_UBUNTU"
		So(ds.Put(ctx, &FunctionRun{
			ID:      functionName,
			Parent:  runKey,
			Workers: []string{workerName},
		}), ShouldBeNil)
		So(ds.Put(ctx, &FunctionRunResult{
			ID:     1,
			Parent: functionKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, functionKey)
		So(ds.Put(ctx, &WorkerRun{
			ID:       workerName,
			Parent:   functionKey,
			Platform: platform,
		}), ShouldBeNil)
		So(ds.Put(ctx, &Comment{
			Parent:  workerKey,
			Comment: []byte("Hello"),
		}), ShouldBeNil)

		Convey("FetchFunctionRuns with results", func() {
			functionRuns, err := FetchFunctionRuns(ctx, runID)
			So(len(functionRuns), ShouldEqual, 1)
			So(err, ShouldBeNil)
		})

		Convey("FetchFunctionRuns without results", func() {
			functionRuns, err := FetchFunctionRuns(ctx, runID+1)
			So(len(functionRuns), ShouldEqual, 0)
			So(err, ShouldBeNil)
		})

		Convey("FetchComments with results", func() {
			functionRuns, err := FetchComments(ctx, runID)
			So(len(functionRuns), ShouldEqual, 1)
			So(err, ShouldBeNil)
		})

		Convey("FetchComments without results", func() {
			functionRuns, err := FetchFunctionRuns(ctx, runID+1)
			So(len(functionRuns), ShouldEqual, 0)
			So(err, ShouldBeNil)
		})
	})
}
