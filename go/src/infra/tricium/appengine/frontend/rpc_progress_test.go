// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/grpc/grpcutil"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"google.golang.org/grpc/codes"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

func TestProgress(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
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
			Functions: []string{functionName},
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
			Function:    functionName,
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
			ID:    gerritMappingID(host, project, change, revision),
			RunID: runID,
		}
		So(ds.Put(ctx, g), ShouldBeNil)

		Convey("Progress request handler", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						Change:  fmt.Sprintf("%s~master~%s", project, changeIDFooter),
						GitRef:  revision,
					},
				},
			}
			response, err := server.Progress(ctx, request)
			So(err, ShouldBeNil)
			So(response, ShouldResemble, &tricium.ProgressResponse{
				RunId: strconv.FormatInt(runID, 10),
				State: tricium.State_SUCCESS,
				FunctionProgress: []*tricium.FunctionProgress{
					{
						Name:        "Hello",
						Platform:    tricium.Platform_UBUNTU,
						State:       tricium.State_SUCCESS,
						NumComments: 1,
					},
				},
			})
		})

		Convey("Progress request handler with Gerrit patch not found", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						Change:  fmt.Sprintf("%s~master~%s", project, changeIDFooter),
						GitRef:  "refs/changes/97/97/2",
					},
				},
			}
			response, err := server.Progress(ctx, request)
			So(response, ShouldResemble, &tricium.ProgressResponse{})
			So(err, ShouldBeNil)
		})

		Convey("Validate request with valid run ID", func() {
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_RunId{
					RunId: "12345",
				},
			}
			id, err := validateProgressRequest(ctx, request)
			So(id, ShouldEqual, 12345)
			So(err, ShouldBeNil)
		})

		Convey("Validate request with invalid run ID", func() {
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_RunId{
					RunId: "not a valid run ID",
				},
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
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						Change:  fmt.Sprintf("%s~master~%s", project, changeIDFooter),
						GitRef:  revision,
					},
				},
			}
			id, err := validateProgressRequest(ctx, request)
			So(id, ShouldEqual, runID)
			So(err, ShouldBeNil)
		})

		Convey("Validate request with valid Gerrit details but no stored run", func() {
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						Change:  fmt.Sprintf("%s~master~%s", project, changeIDFooter),
						GitRef:  "refs/changes/97/97/2",
					},
				},
			}
			id, err := validateProgressRequest(ctx, request)
			So(id, ShouldEqual, 0)
			So(grpcutil.Code(err), ShouldEqual, codes.OK)
		})

		Convey("Validate request with missing Gerrit change ID", func() {
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						GitRef:  revision,
					},
				},
			}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)

		})
		Convey("Validate request with invalid Gerrit change ID", func() {
			request := &tricium.ProgressRequest{
				Source: &tricium.ProgressRequest_GerritRevision{
					GerritRevision: &tricium.GerritRevision{
						Host:    host,
						Project: project,
						Change:  "not a change ID",
						GitRef:  revision,
					},
				},
			}
			_, err := validateProgressRequest(ctx, request)
			So(err, ShouldNotBeNil)
		})
	})
}
