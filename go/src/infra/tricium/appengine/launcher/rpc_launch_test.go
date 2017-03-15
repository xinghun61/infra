// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package launcher

import (
	"errors"
	"testing"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"

	. "github.com/smartystreets/goconvey/convey"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

// mockConfigProvider mocks the common.WorkflowProvider interface.
type mockConfigProvider struct {
}

func (*mockConfigProvider) ReadConfigForProject(c context.Context, project string) (*admin.Workflow, error) {
	return &admin.Workflow{
		Workers: []*admin.Worker{
			{
				Name:  "Hello",
				Needs: tricium.Data_GIT_FILE_DETAILS,
			},
			{
				Name:  "World",
				Needs: tricium.Data_GIT_FILE_DETAILS,
			},
			{
				Name:  "Goodbye",
				Needs: tricium.Data_CLANG_DETAILS,
			},
		},
	}, nil
}
func (*mockConfigProvider) ReadConfigForRun(c context.Context, runID int64) (*admin.Workflow, error) {
	return nil, errors.New("Should not ask for a config using a run ID")
}

func TestLaunchRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)
		Convey("Launch request", func() {
			err := launch(ctx, &admin.LaunchRequest{
				RunId:   runID,
				Project: "test-project",
				GitRef:  "ref/test",
				Paths: []string{
					"README.md",
					"README2.md",
				},
			}, &mockConfigProvider{}, &common.MockIsolator{})
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Stores workflow config", func() {
				wf := &common.Workflow{ID: runID}
				err := ds.Get(ctx, wf)
				So(err, ShouldBeNil)
			})

			Convey("Enqueues driver requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 2)
			})

			// Check guard: one more launch request results in no added tasks
			err = launch(ctx, &admin.LaunchRequest{
				RunId:   runID,
				Project: "test-project",
				GitRef:  "ref/test",
				Paths: []string{
					"README.md",
					"README2.md",
				},
			}, &mockConfigProvider{}, &common.MockIsolator{})
			So(err, ShouldBeNil)

			Convey("Succeeding launch request for the same run enqueues no track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

		})
	})
}
