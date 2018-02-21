// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"encoding/json"
	"errors"
	"testing"

	ds "go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"

	"golang.org/x/net/context"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

// MockIsolator mocks the Isolator interface for testing.
type mockIsolator struct{}

func (*mockIsolator) IsolateGitFileDetails(c context.Context, serverURL string, d *tricium.Data_GitFileDetails) (string, error) {
	return "mockmockmock", nil
}
func (*mockIsolator) IsolateWorker(c context.Context, serverURL string, worker *admin.Worker, inputIsolate string) (string, error) {
	return "mockmockmock", nil
}
func (*mockIsolator) LayerIsolates(c context.Context, serverURL, isolatedInput, isolatedOutput string) (string, error) {
	return "mockmockmock", nil
}
func (*mockIsolator) FetchIsolatedResults(c context.Context, serverURL, isolatedOutput string) (string, error) {
	result := &tricium.Data_Results{
		Comments: []*tricium.Data_Comment{
			{
				Message: "Hello",
			},
		},
	}
	res, err := json.Marshal(result)
	if err != nil {
		return "", errors.New("failed to marshal mock result")
	}
	return string(res), nil
}

func TestWorkerDoneRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		name, _, err := track.ExtractFunctionPlatform(fileIsolator)
		So(err, ShouldBeNil)

		// Add pending workflow run.
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

		// Mark workflow as launched.
		err = workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
			RunId: request.ID,
		}, mockWorkflowProvider{})
		So(err, ShouldBeNil)

		// Mark worker as launched.
		err = workerLaunched(ctx, &admin.WorkerLaunchedRequest{
			RunId:  request.ID,
			Worker: fileIsolator,
		})
		So(err, ShouldBeNil)

		// Mark worker as done.
		err = workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:    request.ID,
			Worker:   fileIsolator,
			Provides: tricium.Data_FILES,
			State:    tricium.State_SUCCESS,
		}, &mockIsolator{})
		So(err, ShouldBeNil)

		functionRun := ds.NewKey(ctx, "FunctionRun", name, 0, runKey)

		Convey("Marks worker as done", func() {
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolator, 0, functionRun)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_SUCCESS)
		})

		Convey("Marks aborted worker as done", func() {
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolator, 0, functionRun)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_SUCCESS)
		})

		Convey("Marks function as done and adds no comments", func() {
			fr := &track.FunctionRunResult{ID: 1, Parent: functionRun}
			So(ds.Get(ctx, fr), ShouldBeNil)
			So(fr.State, ShouldEqual, tricium.State_SUCCESS)
		})

		// Mark multi-platform function as done on one platform.
		err = workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:    request.ID,
			Worker:   clangIsolatorWindows,
			Provides: tricium.Data_RESULTS,
			State:    tricium.State_SUCCESS,
		}, &mockIsolator{})
		So(err, ShouldBeNil)

		Convey("Multi-platform function is half done, function stays launched", func() {
			ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			So(ds.Get(ctx, ar), ShouldBeNil)
			So(ar.State, ShouldEqual, tricium.State_RUNNING)
		})

		// Mark multi-platform function as done on other platform.
		err = workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:    request.ID,
			Worker:   clangIsolatorUbuntu,
			Provides: tricium.Data_RESULTS,
			State:    tricium.State_SUCCESS,
		}, &mockIsolator{})
		So(err, ShouldBeNil)

		Convey("Marks workflow as done and adds comments", func() {
			wr := &track.WorkflowRunResult{ID: 1, Parent: runKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_SUCCESS)
			So(wr.NumComments, ShouldEqual, 2)
		})

		Convey("Marks request as done", func() {
			ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			So(ds.Get(ctx, ar), ShouldBeNil)
			So(ar.State, ShouldEqual, tricium.State_SUCCESS)
		})
	})
}
