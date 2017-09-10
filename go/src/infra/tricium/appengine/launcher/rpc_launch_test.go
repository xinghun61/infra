// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package launcher

import (
	"testing"

	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"

	. "github.com/smartystreets/goconvey/convey"

	"golang.org/x/net/context"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	trit "infra/tricium/appengine/common/testing"
)

const (
	hello        = "Hello"
	fileIsolator = "FileIsolator"
	pylint       = "PyLint"
	project      = "playground/gerrit-tricium"
)

// mockConfigProvider mocks the common.WorkflowProvider interface.
type mockConfigProvider struct {
}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{
		SwarmingServer: "chromium-swarm-dev",
		IsolateServer:  "isolatedserver-dev",
		Projects: []*tricium.ProjectDetails{
			{
				Name: project,
				SwarmingServiceAccount: "swarming@email.com",
			},
		},
		Platforms: []*tricium.Platform_Details{
			{
				Name:       tricium.Platform_UBUNTU,
				Dimensions: []string{"pool:Chrome", "os:Ubuntu14.04"},
				HasRuntime: true,
			},
		},
		DataDetails: []*tricium.Data_TypeDetails{
			{
				Type:               tricium.Data_GIT_FILE_DETAILS,
				IsPlatformSpecific: false,
			},
			{
				Type:               tricium.Data_FILES,
				IsPlatformSpecific: false,
			},
			{
				Type:               tricium.Data_CLANG_DETAILS,
				IsPlatformSpecific: true,
			},
			{
				Type:               tricium.Data_RESULTS,
				IsPlatformSpecific: true,
			},
		},
		Analyzers: []*tricium.Analyzer{
			{
				Name:     hello,
				Needs:    tricium.Data_GIT_FILE_DETAILS,
				Provides: tricium.Data_RESULTS,
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: tricium.Platform_UBUNTU,
						RuntimePlatform:     tricium.Platform_UBUNTU,
						Impl: &tricium.Impl_Cmd{
							Cmd: &tricium.Cmd{
								Exec: "hello",
							},
						},
						Deadline: 120,
					},
				},
			},
			{
				Name:     fileIsolator,
				Needs:    tricium.Data_GIT_FILE_DETAILS,
				Provides: tricium.Data_FILES,
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: tricium.Platform_UBUNTU,
						RuntimePlatform:     tricium.Platform_UBUNTU,
						Impl: &tricium.Impl_Cmd{
							Cmd: &tricium.Cmd{
								Exec: "fileisolator",
							},
						},
						Deadline: 120,
					},
				},
			},
			{
				Name:     pylint,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: tricium.Platform_UBUNTU,
						RuntimePlatform:     tricium.Platform_UBUNTU,
						Impl: &tricium.Impl_Cmd{
							Cmd: &tricium.Cmd{
								Exec: "pylint",
							},
						},
						Deadline: 120,
					},
				},
			},
		},
	}, nil
}

func (*mockConfigProvider) GetProjectConfig(c context.Context, project string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{
		Name: project,
		Selections: []*tricium.Selection{
			{
				Analyzer: fileIsolator,
				Platform: tricium.Platform_UBUNTU,
			},
			{
				Analyzer: hello,
				Platform: tricium.Platform_UBUNTU,
			},
			{
				Analyzer: pylint,
				Platform: tricium.Platform_UBUNTU,
			},
		},
	}, nil
}

func TestLaunchRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)
		Convey("Launch request", func() {
			err := launch(ctx, &admin.LaunchRequest{
				RunId:   runID,
				Project: project,
				GitRef:  "ref/test",
				Paths: []string{
					"README.md",
					"README2.md",
				},
			}, &mockConfigProvider{}, common.MockIsolator, common.MockSwarmingAPI, common.MockPubSub)
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Stores workflow config", func() {
				wf := &config.Workflow{ID: runID}
				err := ds.Get(ctx, wf)
				So(err, ShouldBeNil)
			})

			Convey("Enqueues driver requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 2)
			})

			// Check guard: one more launch request results in no added tasks.
			err = launch(ctx, &admin.LaunchRequest{
				RunId:   runID,
				Project: "test-project",
				GitRef:  "ref/test",
				Paths: []string{
					"README.md",
					"README2.md",
				},
			}, config.MockProvider, common.MockIsolator, common.MockSwarmingAPI, common.MockPubSub)
			So(err, ShouldBeNil)

			Convey("Succeeding launch request for the same run enqueues no track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

		})
	})
}
