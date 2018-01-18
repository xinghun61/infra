// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"strconv"
	"testing"

	ds "go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestProjectProgress(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &trit.Testing{}
		ctx := tt.Context()
		var runID int64 = 22

		// Add completed request.
		request := &track.AnalyzeRequest{
			ID:      runID,
			Project: project,
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		So(ds.Put(ctx, &track.AnalyzeRequestResult{
			ID:     1,
			Parent: requestKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		analyzerName := "Hello"
		run := &track.WorkflowRun{
			ID:        1,
			Parent:    requestKey,
			Analyzers: []string{analyzerName},
		}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			ID:     1,
			Parent: runKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		platform := tricium.Platform_UBUNTU
		analyzerKey := ds.NewKey(ctx, "AnalyzerRun", analyzerName, 0, runKey)
		workerName := analyzerName + "_UBUNTU"
		So(ds.Put(ctx, &track.FunctionRun{
			ID:      analyzerName,
			Parent:  runKey,
			Workers: []string{workerName},
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:          1,
			Parent:      analyzerKey,
			State:       tricium.State_SUCCESS,
			NumComments: 2, // NB! Only adding aggregated data and not the corresponding comments.
		}), ShouldBeNil)
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, analyzerKey)
		worker := &track.WorkerRun{
			ID:       workerName,
			Parent:   analyzerKey,
			Platform: platform,
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		workerKey = ds.KeyForObj(ctx, worker)
		So(ds.Put(ctx, &track.WorkerRunResult{
			ID:          1,
			Parent:      workerKey,
			Analyzer:    analyzerName,
			Platform:    tricium.Platform_UBUNTU,
			State:       tricium.State_SUCCESS,
			NumComments: 1,
		}), ShouldBeNil)

		Convey("Project progress request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			runProgress, _, err := projectProgress(ctx, project, &mockConfigProvider{})
			So(err, ShouldBeNil)
			So(len(runProgress), ShouldEqual, 1)
			So(runProgress[0].RunId, ShouldEqual, strconv.FormatInt(runID, 10))
			So(runProgress[0].State, ShouldEqual, tricium.State_SUCCESS)
			So(runProgress[0].NumComments, ShouldEqual, 2)
		})

		Convey("Validate request with project", func() {
			request := &tricium.ProjectProgressRequest{
				Project: project,
			}
			p, err := validateProjectProgressRequest(ctx, request)
			So(err, ShouldBeNil)
			So(p, ShouldEqual, project)
		})

		Convey("Validate request with missing project", func() {
			request := &tricium.ProjectProgressRequest{}
			_, err := validateProjectProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})
	})
}
