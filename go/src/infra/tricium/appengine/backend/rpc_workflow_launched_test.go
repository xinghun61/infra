// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestWorkflowLaunchedRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		clangIsolatorUbuntu := "ClangIsolator_Ubuntu"
		clangIsolatorWindows := "ClangIsolator_Windows"
		fileIsolator := "GitFileIsolator_Ubuntu"

		workflowProvider := &mockWorkflowProvider{
			Workflow: &admin.Workflow{
				Workers: []*admin.Worker{
					{
						Name:  clangIsolatorUbuntu,
						Needs: tricium.Data_FILES,
					},
					{
						Name:  clangIsolatorWindows,
						Needs: tricium.Data_FILES,
					},
					{
						Name:  fileIsolator,
						Needs: tricium.Data_GIT_FILE_DETAILS,
						Next: []string{
							clangIsolatorUbuntu,
							clangIsolatorWindows,
						},
					},
				},
			},
		}

		Convey("Trivial workflow with no analyzers is marked done immediately", func() {
			request := &track.AnalyzeRequest{}
			So(ds.Put(ctx, request), ShouldBeNil)
			requestKey := ds.KeyForObj(ctx, request)
			run := &track.WorkflowRun{ID: 1, Parent: requestKey}
			So(ds.Put(ctx, run), ShouldBeNil)
			runKey := ds.KeyForObj(ctx, run)
			runResult := &track.WorkflowRunResult{
				ID:     1,
				Parent: runKey,
				State:  tricium.State_PENDING,
			}
			So(ds.Put(ctx, runResult), ShouldBeNil)

			// Use a mock workflow with no workers (and thus no functions).
			emptyWorkflowProvider := &mockWorkflowProvider{
				Workflow: &admin.Workflow{Workers: nil},
			}

			// Call workflowLaunched.
			err := workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
				RunId: request.ID,
			}, emptyWorkflowProvider)
			So(err, ShouldBeNil)

			Convey("Marks workflow run as (trivially) done", func() {
				So(ds.Get(ctx, runResult), ShouldBeNil)
				So(runResult.State, ShouldEqual, tricium.State_SUCCESS)
			})

			Convey("There are no functions in this fun", func() {
				So(ds.Get(ctx, run), ShouldBeNil)
				So(len(run.Functions), ShouldEqual, 0)
			})
		})

		Convey("Workflow request", func() {
			// Add pending workflow run entity.
			request := &track.AnalyzeRequest{}
			So(ds.Put(ctx, request), ShouldBeNil)
			requestKey := ds.KeyForObj(ctx, request)
			run := &track.WorkflowRun{ID: 1, Parent: requestKey}
			So(ds.Put(ctx, run), ShouldBeNil)
			runKey := ds.KeyForObj(ctx, run)
			runResult := &track.WorkflowRunResult{
				ID:     1,
				Parent: runKey,
				State:  tricium.State_PENDING,
			}
			So(ds.Put(ctx, runResult), ShouldBeNil)

			// Mark workflow as launched.
			err := workflowLaunched(ctx, &admin.WorkflowLaunchedRequest{
				RunId: request.ID,
			}, workflowProvider)
			So(err, ShouldBeNil)

			name, _, err := track.ExtractFunctionPlatform(fileIsolator)

			Convey("Marks workflow run as launched", func() {
				So(ds.Get(ctx, runResult), ShouldBeNil)
				So(runResult.State, ShouldEqual, tricium.State_RUNNING)
			})

			Convey("Adds list of functions to WorkflowRun", func() {
				So(ds.Get(ctx, run), ShouldBeNil)
				So(len(run.Functions), ShouldEqual, 3)
			})

			Convey("Worker and function is marked pending", func() {
				So(err, ShouldBeNil)
				functionRunKey := ds.NewKey(ctx, "FunctionRun", name, 0, runKey)
				workerKey := ds.NewKey(ctx, "WorkerRun", fileIsolator, 0, functionRunKey)
				wr := &track.WorkerRunResult{ID: 1, Parent: workerKey}
				So(ds.Get(ctx, wr), ShouldBeNil)
				So(wr.State, ShouldEqual, tricium.State_PENDING)
				fr := &track.FunctionRunResult{ID: 1, Parent: functionRunKey}
				So(ds.Get(ctx, fr), ShouldBeNil)
				So(fr.State, ShouldEqual, tricium.State_PENDING)
			})
		})
	})
}
