// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package track

import (
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

const (
	project    = "playground/gerrit-tricium"
	okACLUser  = "user:ok@example.com"
	okACLGroup = "tricium-playground-requesters"
)

// mockConfigProvider mocks the common.ConfigProvider interface.
// TODO(qyearsley): Consider adding maps of configs in MockProvider
// in common/config/provider.go to reduce duplication in tests.
type mockConfigProvider struct{}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{}, nil
}

func (*mockConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	if p == project {
		return &tricium.ProjectConfig{
			Acls: []*tricium.Acl{
				{
					Role:     tricium.Acl_READER,
					Identity: okACLUser,
				},
				{
					Role:     tricium.Acl_REQUESTER,
					Identity: okACLUser,
				},
			},
		}, nil
	}
	return &tricium.ProjectConfig{}, nil
}

func (*mockConfigProvider) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	return nil, nil // not used in this test
}

func TestFetchRecentRequests(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &triciumtest.Testing{}
		ctx := tt.Context()

		request := &AnalyzeRequest{Project: project}
		So(ds.Put(ctx, request), ShouldBeNil)

		Convey("FetchRecentRequests ok user", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity:       okACLUser,
				IdentityGroups: []string{okACLGroup},
			})
			rs, err := FetchRecentRequests(ctx, &mockConfigProvider{})
			So(err, ShouldBeNil)
			So(rs, ShouldResemble, []*AnalyzeRequest{request})
		})

		Convey("FetchRecentRequests other user", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: "user:other@example.com",
			})
			rs, err := FetchRecentRequests(ctx, &mockConfigProvider{})
			So(err, ShouldBeNil)
			So(len(rs), ShouldEqual, 0)
		})
	})
}

func TestTrackHelperFunctions(t *testing.T) {
	Convey("Test Environment", t, func() {

		tt := &triciumtest.Testing{}
		ctx := tt.Context()

		// Add completed request.
		request := &AnalyzeRequest{}
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
		functionRunResult := &FunctionRunResult{
			ID:     1,
			Parent: functionKey,
			State:  tricium.State_SUCCESS,
		}
		So(ds.Put(ctx, functionRunResult), ShouldBeNil)
		workerKey := ds.NewKey(ctx, "WorkerRun", workerName, 0, functionKey)
		So(ds.Put(ctx, &WorkerRun{
			ID:       workerName,
			Parent:   functionKey,
			Platform: platform,
		}), ShouldBeNil)
		So(ds.Put(ctx, &Comment{
			Parent:  workerKey,
			Comment: []byte("Hello comment"),
		}), ShouldBeNil)

		Convey("FetchFunctionRuns with results", func() {
			functionRuns, err := FetchFunctionRuns(ctx, request.ID)
			So(len(functionRuns), ShouldEqual, 1)
			So(functionRuns[0].ID, ShouldEqual, "Hello")
			So(err, ShouldBeNil)
		})

		Convey("FetchFunctionRuns without results", func() {
			functionRuns, err := FetchFunctionRuns(ctx, request.ID+1)
			So(len(functionRuns), ShouldEqual, 0)
			So(err, ShouldBeNil)
		})

		Convey("FetchComments with results", func() {
			comments, err := FetchComments(ctx, request.ID)
			So(len(comments), ShouldEqual, 1)
			So(string(comments[0].Comment), ShouldEqual, "Hello comment")
			So(err, ShouldBeNil)
		})

		Convey("FetchComments without results", func() {
			comments, err := FetchComments(ctx, request.ID+1)
			So(len(comments), ShouldEqual, 0)
			So(err, ShouldBeNil)
		})

		Convey("FetchWorkerRuns with results", func() {
			workerRuns, err := FetchWorkerRuns(ctx, request.ID)
			So(len(workerRuns), ShouldEqual, 1)
			So(workerRuns[0].ID, ShouldEqual, "Hello_UBUNTU")
			So(err, ShouldBeNil)
		})

		Convey("FetchWorkerRuns without results", func() {
			workerRuns, err := FetchWorkerRuns(ctx, request.ID+1)
			So(len(workerRuns), ShouldEqual, 0)
			So(err, ShouldBeNil)
		})
	})
}
