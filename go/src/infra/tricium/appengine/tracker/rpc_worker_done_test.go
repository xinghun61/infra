// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"testing"

	"github.com/golang/protobuf/jsonpb"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"golang.org/x/net/context"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

// MockIsolator mocks the Isolator interface for testing.
type mockIsolator struct{}

func (*mockIsolator) IsolateGitFileDetails(c context.Context, serverURL string, d *tricium.Data_GitFileDetails) (string, error) {
	return "", nil
}
func (*mockIsolator) IsolateWorker(c context.Context, serverURL string, worker *admin.Worker, inputIsolate string) (string, error) {
	return "", nil
}
func (*mockIsolator) LayerIsolates(c context.Context, serverURL, isolatedInput, isolatedOutput string) (string, error) {
	return "", nil
}
func (*mockIsolator) FetchIsolatedResults(c context.Context, serverURL, isolatedOutput string) (string, error) {
	result := &tricium.Data_Results{
		Comments: []*tricium.Data_Comment{
			{Message: "Hello"},
		},
	}
	return (&jsonpb.Marshaler{}).MarshalToString(result)
}

func TestWorkerDoneRequest(t *testing.T) {
	Convey("Worker done request with successful worker", t, func() {
		ctx := triciumtest.Context()

		fileIsolatorUbuntu := "GitFileIsolator_Ubuntu"
		fileIsolator := "GitFileIsolator"
		clangIsolatorUbuntu := "ClangIsolator_Ubuntu"
		clangIsolatorWindows := "ClangIsolator_Windows"

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
		So(workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
			RunId: request.ID,
		}, mockWorkflowProvider{}), ShouldBeNil)

		// Mark worker as launched.
		So(workerLaunched(ctx, &admin.WorkerLaunchedRequest{
			RunId:  request.ID,
			Worker: fileIsolatorUbuntu,
		}), ShouldBeNil)

		// Mark worker as done.
		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             fileIsolatorUbuntu,
			Provides:           tricium.Data_FILES,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "bas3ba11",
		}, &mockIsolator{}), ShouldBeNil)

		functionKey := ds.NewKey(ctx, "FunctionRun", fileIsolator, 0, runKey)

		Convey("Marks worker as done", func() {
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolatorUbuntu, 0, functionKey)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_SUCCESS)
		})

		Convey("Marks function as done and adds no comments", func() {
			fr := &track.FunctionRunResult{ID: 1, Parent: functionKey}
			So(ds.Get(ctx, fr), ShouldBeNil)
			So(fr.State, ShouldEqual, tricium.State_SUCCESS)
		})

		// Mark multi-platform function as done on one platform.
		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             clangIsolatorWindows,
			Provides:           tricium.Data_RESULTS,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "1234",
		}, &mockIsolator{}), ShouldBeNil)

		Convey("Multi-platform function is half done, request stays launched", func() {
			ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			So(ds.Get(ctx, ar), ShouldBeNil)
			So(ar.State, ShouldEqual, tricium.State_RUNNING)
		})

		// Mark multi-platform function as done on other platform.
		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             clangIsolatorUbuntu,
			Provides:           tricium.Data_RESULTS,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "1234",
		}, &mockIsolator{}), ShouldBeNil)

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

func TestAbortedWorkerDoneRequest(t *testing.T) {
	Convey("Worker done request with an aborted worker", t, func() {
		// This test is similar to the case above, except that one of
		// the workers is aborted, so the function is considered
		// failed, and thus the workflow run is failed.
		ctx := triciumtest.Context()

		fileIsolatorUbuntu := "GitFileIsolator_Ubuntu"
		fileIsolator := "GitFileIsolator"

		// Add pending run entry.
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
		So(workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
			RunId: request.ID,
		}, mockWorkflowProvider{}), ShouldBeNil)

		// Mark worker as launched.
		So(workerLaunched(ctx, &admin.WorkerLaunchedRequest{
			RunId:  request.ID,
			Worker: fileIsolatorUbuntu,
		}), ShouldBeNil)

		// Mark worker as done.
		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             fileIsolatorUbuntu,
			State:              tricium.State_ABORTED,
			IsolatedOutputHash: "bas3ba11",
		}, &mockIsolator{}), ShouldBeNil)

		functionKey := ds.NewKey(ctx, "FunctionRun", fileIsolator, 0, runKey)

		Convey("WorkerRun is marked as aborted", func() {
			workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolatorUbuntu, 0, functionKey)
			wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_ABORTED)
		})

		Convey("FunctionRun is failed, with no comments", func() {
			fr := &track.FunctionRunResult{ID: 1, Parent: functionKey}
			So(ds.Get(ctx, fr), ShouldBeNil)
			So(fr.State, ShouldEqual, tricium.State_FAILURE)
		})

		// Mark other workers as done.
		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             clangIsolatorUbuntu,
			Provides:           tricium.Data_RESULTS,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "1234",
		}, &mockIsolator{}), ShouldBeNil)

		So(workerDone(ctx, &admin.WorkerDoneRequest{
			RunId:              request.ID,
			Worker:             clangIsolatorWindows,
			Provides:           tricium.Data_RESULTS,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "1234",
		}, &mockIsolator{}), ShouldBeNil)

		Convey("WorkflowRun is marked as failed", func() {
			wr := &track.WorkflowRunResult{ID: 1, Parent: runKey}
			So(ds.Get(ctx, wr), ShouldBeNil)
			So(wr.State, ShouldEqual, tricium.State_FAILURE)
		})

		Convey("AnalyzeRequest is marked as failed", func() {
			ar := &track.AnalyzeRequestResult{ID: 1, Parent: requestKey}
			So(ds.Get(ctx, ar), ShouldBeNil)
			So(ar.State, ShouldEqual, tricium.State_FAILURE)
		})
	})
}

func TestValidateWorkerDoneRequestRequest(t *testing.T) {
	Convey("Request with all parts is valid", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:              1234,
			Worker:             "MyLint_Ubuntu",
			Provides:           tricium.Data_RESULTS,
			State:              tricium.State_SUCCESS,
			IsolatedOutputHash: "12ab34cd",
		}), ShouldBeNil)
	})

	Convey("Specifying provides and state is optional", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:              1234,
			Worker:             "MyLint_Ubuntu",
			IsolatedOutputHash: "12ab34cd",
		}), ShouldBeNil)
	})

	Convey("Request with no run ID is invalid", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			Worker:             "MyLint_Ubuntu",
			IsolatedOutputHash: "12ab34cd",
		}), ShouldNotBeNil)
	})

	Convey("Request with no worker name invalid", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:              1234,
			IsolatedOutputHash: "12ab34cd",
		}), ShouldNotBeNil)
	})

	Convey("Request with no output is valid", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:  1234,
			Worker: "MyLint_Ubuntu",
		}), ShouldBeNil)
	})

	Convey("Providing buildbucket output but not isolated output is OK", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:             1234,
			Worker:            "MyLint_Ubuntu",
			BuildbucketOutput: "foobar",
		}), ShouldBeNil)
	})

	Convey("Providing both output types is not OK", t, func() {
		So(validateWorkerDoneRequest(&admin.WorkerDoneRequest{
			RunId:              1234,
			Worker:             "MyLint_Ubuntu",
			BuildbucketOutput:  "foobar",
			IsolatedOutputHash: "12ab34cd",
		}), ShouldNotBeNil)
	})
}
