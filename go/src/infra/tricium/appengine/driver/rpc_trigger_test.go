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
			},
			{
				Name:     "World",
				Needs:    tricium.Data_GIT_FILE_DETAILS,
				Provides: tricium.Data_CLANG_DETAILS,
				Next:     []string{"Goodbye"},
			},
			{
				Name:  "Goodbye",
				Needs: tricium.Data_CLANG_DETAILS,
			},
		},
	}, nil
}

func TestTriggerRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &triciumtest.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)

		Convey("Driver trigger request", func() {
			err := trigger(ctx, &admin.TriggerRequest{
				RunId:  runID,
				Worker: "Hello",
			}, mockWorkflowProvider{}, common.MockSwarmingAPI, common.MockIsolator)
			So(err, ShouldBeNil)
			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})
		})
	})
}

func TestHelperFunctions(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &triciumtest.Testing{}
		ctx := tt.Context()

		So(ds.Put(ctx, &track.AnalyzeRequest{
			ID:             1,
			Project:        "my-luci-config-project-id",
			GitRepo:        "http://my-gerrit.com/my-project",
			GitRef:         "refs/changes/97/597/2",
			Paths:          []string{"README.md"},
			Consumer:       tricium.Consumer_GERRIT,
			GerritProject:  "my-project",
			GerritChange:   "my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
			GerritRevision: "refs/changes/97/597/2",
		}), ShouldBeNil)

		So(ds.Put(ctx, &track.AnalyzeRequest{
			ID:      2,
			Project: "another-luci-config-project-id",
			GitRepo: "http://my-nongerrit.com/repo-url",
			GitRef:  "refs/foo",
			Paths:   []string{"README.md"},
		}), ShouldBeNil)

		Convey("Swarming tags include Gerrit details for Gerrit requests", func() {
			So(swarmingTags(ctx, "Spacey_UBUNTU", 1), ShouldResemble, []string{
				"tricium:1",
				"function:Spacey",
				"platform:UBUNTU",
				"gerrit_project:my-project",
				"gerrit_change:my-project~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
				"gerrit_cl_number:597",
				"gerrit_patch_set:2",
			})

		})

		Convey("Swarming tags omit Gerrit details for non-Gerrit requests", func() {
			So(swarmingTags(ctx, "Pylint_UBUNTU", 2), ShouldResemble, []string{
				"tricium:1",
				"function:Pylint",
				"platform:UBUNTU",
			})

		})

		Convey("Swarming tags omit Gerrit details if run not found", func() {
			So(swarmingTags(ctx, "Spacey_UBUNTU", 3), ShouldResemble, []string{
				"tricium:1",
				"function:Spacey",
				"platform:UBUNTU",
			})
		})

		Convey("Swarming tags are nil for invalid worker names", func() {
			So(swarmingTags(ctx, "invalidworker", 1), ShouldBeNil)
		})
	})
}
