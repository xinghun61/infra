// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

// mockConfigProvider mocks common.WorkflowProvider.
type mockWorkflowProvider struct {
}

func (mockWorkflowProvider) GetWorkflow(c context.Context, runID int64) (*admin.Workflow, error) {
	return &admin.Workflow{
		Workers: []*admin.Worker{
			{
				Name:  "Hello",
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Impl:  &admin.Worker_Cmd{},
			},
			{
				Name:     "World",
				Needs:    tricium.Data_GIT_FILE_DETAILS,
				Provides: tricium.Data_CLANG_DETAILS,
				Impl:     &admin.Worker_Cmd{},
				Next:     []string{"Goodbye"},
			},
			{
				Name:  "Goodbye",
				Needs: tricium.Data_CLANG_DETAILS,
				Impl:  &admin.Worker_Recipe{},
			},
		},
	}, nil
}

func TestTriggerRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		runID := int64(123456789)

		Convey("Driver trigger request", func() {
			err := trigger(ctx, &admin.TriggerRequest{
				RunId:  runID,
				Worker: "Hello",
			}, mockWorkflowProvider{}, common.MockTaskServerAPI, common.MockTaskServerAPI, common.MockIsolator)
			So(err, ShouldBeNil)
			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})
		})
	})
}

func TestHelperFunctions(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		So(ds.Put(ctx, &track.AnalyzeRequest{
			ID:            123,
			Project:       "my-luci-config-project-id",
			GitURL:        "http://my-gerrit.com/my-project",
			GitRef:        "refs/changes/97/597/2",
			Paths:         []string{"README.md"},
			GerritProject: "my-project",
			GerritChange:  "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
		}), ShouldBeNil)

		So(ds.Put(ctx, &track.AnalyzeRequest{
			ID:      321,
			Project: "another-luci-config-project-id",
			GitURL:  "http://my-nongerrit.com/repo-url",
			GitRef:  "refs/foo",
			Paths:   []string{"README.md"},
		}), ShouldBeNil)

		Convey("Swarming tags include Gerrit details for Gerrit requests", func() {
			gerrit := fetchGerritDetails(ctx, 123)
			So(gerrit.project, ShouldEqual, "my-project")
			So(gerrit.change, ShouldEqual, "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940")
			So(gerrit.cl, ShouldEqual, "597")
			So(gerrit.patch, ShouldEqual, "2")
			So(swarmingTags(ctx, "Spacey_UBUNTU", 123, gerrit), ShouldResemble, []string{
				"function:Spacey",
				"platform:UBUNTU",
				"run_id:123",
				"tricium:1",
				"gerrit_project:my-project",
				"gerrit_change:my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
				"gerrit_cl_number:597",
				"gerrit_patch_set:2",
			})
		})

		Convey("Gerrit props populate Gerrit details for Gerrit requests", func() {
			gerrit := fetchGerritDetails(ctx, 123)
			So(gerrit.project, ShouldEqual, "my-project")
			So(gerrit.change, ShouldEqual, "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940")
			So(gerrit.cl, ShouldEqual, "597")
			So(gerrit.patch, ShouldEqual, "2")
			gerritProps := gerritProperties(ctx, gerrit)
			So(gerritProps["gerrit_project"], ShouldEqual, "my-project")
			So(gerritProps["gerrit_change"], ShouldEqual, "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940")
			So(gerritProps["gerrit_cl_number"], ShouldEqual, "597")
			So(gerritProps["gerrit_patch_set"], ShouldEqual, "2")
		})

		var gerritProps gerritDetails

		Convey("Swarming tags omit Gerrit details for non-Gerrit requests", func() {
			gerrit := fetchGerritDetails(ctx, 321)
			So(gerrit, ShouldResemble, gerritProps)
			So(swarmingTags(ctx, "Pylint_UBUNTU", 321, gerrit), ShouldResemble, []string{
				"function:Pylint",
				"platform:UBUNTU",
				"run_id:321",
				"tricium:1",
			})
		})

		Convey("Swarming tags omit Gerrit details if run not found", func() {
			gerrit := fetchGerritDetails(ctx, 789)
			So(gerrit, ShouldResemble, gerritProps)
			So(swarmingTags(ctx, "Spacey_UBUNTU", 789, gerrit), ShouldResemble, []string{
				"function:Spacey",
				"platform:UBUNTU",
				"run_id:789",
				"tricium:1",
			})
		})

		Convey("Swarming tags are nil for invalid worker names", func() {
			So(swarmingTags(ctx, "invalidworker", 1, gerritProps), ShouldBeNil)
		})
	})
}
