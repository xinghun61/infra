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
			Files:         []tricium.Data_File{{Path: "README.md"}},
			GerritHost:    "http://my-gerrit-review.com/my-project",
			GerritProject: "my-project",
			GerritChange:  "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
			CommitMessage: "My CL summary\n\nBug: 123\n",
		}), ShouldBeNil)

		So(ds.Put(ctx, &track.AnalyzeRequest{
			ID:      321,
			Project: "another-luci-config-project-id",
			GitURL:  "http://my-nongerrit.com/repo-url",
			GitRef:  "refs/foo",
			Files:   []tricium.Data_File{{Path: "README.md"}},
		}), ShouldBeNil)

		Convey("Swarming tags include Gerrit details for Gerrit requests", func() {
			patch := fetchPatchDetails(ctx, 123)
			So(patch.GitilesHost, ShouldEqual, "http://my-gerrit.com/my-project")
			So(patch.GitilesProject, ShouldEqual, "my-luci-config-project-id")
			So(patch.GerritHost, ShouldEqual, "http://my-gerrit-review.com/my-project")
			So(patch.GerritProject, ShouldEqual, "my-project")
			So(patch.GerritChange, ShouldEqual, "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940")
			So(patch.GerritCl, ShouldEqual, "597")
			So(patch.GerritPatch, ShouldEqual, "2")
			So(getTags(ctx, "Spacey_UBUNTU", 123, patch), ShouldResemble, []string{
				"function:Spacey",
				"platform:UBUNTU",
				"run_id:123",
				"tricium:1",
				"gerrit_project:my-project",
				"gerrit_change:my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
				"gerrit_cl_number:597",
				"gerrit_patch_set:2",
				"buildset:patch/gerrit/http://my-gerrit-review.com/my-project/597/2",
			})
		})

		Convey("Swarming tags omit Gerrit details for non-Gerrit requests", func() {
			patch := fetchPatchDetails(ctx, 321)
			expected := common.PatchDetails{
				GitilesHost:    "http://my-nongerrit.com/repo-url",
				GitilesProject: "another-luci-config-project-id",
			}
			So(patch, ShouldResemble, expected)
			So(getTags(ctx, "Pylint_UBUNTU", 321, patch), ShouldResemble, []string{
				"function:Pylint",
				"platform:UBUNTU",
				"run_id:321",
				"tricium:1",
			})
		})

		Convey("Swarming tags omit Gerrit details if run not found", func() {
			patch := fetchPatchDetails(ctx, 789)
			So(patch, ShouldResemble, common.PatchDetails{})
			So(getTags(ctx, "Spacey_UBUNTU", 789, patch), ShouldResemble, []string{
				"function:Spacey",
				"platform:UBUNTU",
				"run_id:789",
				"tricium:1",
			})
		})

		Convey("Swarming tags are nil for invalid worker names", func() {
			So(getTags(ctx, "invalidworker", 1, common.PatchDetails{}), ShouldBeNil)
		})
	})
}
