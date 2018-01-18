// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
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

func TestProgress(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &trit.Testing{}
		ctx := tt.Context()
		var runID int64 = 22

		// Add completed request.
		request := &track.AnalyzeRequest{
			ID: runID,
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		So(ds.Put(ctx, &track.AnalyzeRequestResult{
			ID:     1,
			Parent: requestKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		functionName := "Hello"
		run := &track.WorkflowRun{
			ID:        1,
			Parent:    requestKey,
			Analyzers: []string{functionName},
		}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			ID:     1,
			Parent: runKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		platform := tricium.Platform_UBUNTU
		functionKey := ds.NewKey(ctx, "FunctionRun", functionName, 0, runKey)
		workerName := functionName + "_UBUNTU"
		So(ds.Put(ctx, &track.FunctionRun{
			ID:      functionName,
			Parent:  runKey,
			Workers: []string{workerName},
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:     1,
			Parent: functionKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, functionKey)
		worker := &track.WorkerRun{
			ID:       workerName,
			Parent:   functionKey,
			Platform: platform,
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		workerKey = ds.KeyForObj(ctx, worker)
		So(ds.Put(ctx, &track.WorkerRunResult{
			ID:          1,
			Parent:      workerKey,
			Analyzer:    functionName,
			Platform:    tricium.Platform_UBUNTU,
			State:       tricium.State_SUCCESS,
			NumComments: 1,
		}), ShouldBeNil)

		// Add mapping from Gerrit change to the run ID.
		host := "chromium-review.googlesource.com"
		project := "playground/gerrit-tricium"
		changeIDFooter := "I17e97e23ecf2890bf6b72ffd1d7a3167ed1b0a11"
		change := fmt.Sprintf("%s~master~%s", project, changeIDFooter)
		revision := "refs/changes/97/97/1"
		g := &GerritChangeToRunID{
			ID:    gerritMappingID(host, project, change),
			RunID: runID,
		}
		So(ds.Put(ctx, g), ShouldBeNil)

		Convey("Progress request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			state, progress, _, err := progress(ctx, runID)
			So(err, ShouldBeNil)
			So(state, ShouldEqual, tricium.State_SUCCESS)
			So(len(progress), ShouldEqual, 1)
			So(progress[0].Name, ShouldEqual, functionName)
			So(progress[0].Platform, ShouldEqual, platform)
			So(progress[0].NumComments, ShouldEqual, 1)
			So(progress[0].State, ShouldEqual, tricium.State_SUCCESS)
		})

		Convey("Validate request with valid run ID", func() {
			request := &tricium.ProgressRequest{
				RunId: "12345",
			}
			id, err := validateProgressRequest(ctx, request)
			So(id, ShouldEqual, 12345)
			So(err, ShouldBeNil)
		})

		Convey("Validate request with invalid run ID", func() {
			request := &tricium.ProgressRequest{
				RunId: "invalid, not a number",
			}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})

		Convey("Validate request with no contents", func() {
			request := &tricium.ProgressRequest{}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})

		Convey("Validate request with valid Gerrit details", func() {
			request := &tricium.ProgressRequest{
				Consumer: tricium.Consumer_GERRIT,
				GerritDetails: &tricium.GerritConsumerDetails{
					Host:     host,
					Project:  project,
					Change:   fmt.Sprintf("%s~master~%s", project, changeIDFooter),
					Revision: revision,
				},
			}
			id, err := validateProgressRequest(ctx, request)
			So(id, ShouldEqual, runID)
			So(err, ShouldBeNil)
		})

		Convey("Validate request with missing Gerrit details", func() {
			request := &tricium.ProgressRequest{
				Consumer: tricium.Consumer_GERRIT,
				GerritDetails: &tricium.GerritConsumerDetails{
					Host:     host,
					Project:  project,
					Revision: revision,
				},
			}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})

		Convey("Validate request with both Gerrit details run ID", func() {
			request := &tricium.ProgressRequest{
				RunId:    "76543",
				Consumer: tricium.Consumer_GERRIT,
				GerritDetails: &tricium.GerritConsumerDetails{
					Host:     host,
					Project:  project,
					Change:   fmt.Sprintf("%s~master~%s", project, changeIDFooter),
					Revision: revision,
				},
			}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})
	})
}
