// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"errors"
	"testing"

	"golang.org/x/net/context"

	tq "github.com/luci/gae/service/taskqueue"
	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

// mockConfigProvider mocks common.WorkflowProvider.
type mockConfigProvider struct {
}

func (*mockConfigProvider) ReadConfigForProject(c context.Context, project string) (*admin.Workflow, error) {
	return nil, errors.New("Should not try to retrieve workflow config from project name")
}
func (*mockConfigProvider) ReadConfigForRun(c context.Context, runID int64) (*admin.Workflow, error) {
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
		tt := &trit.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)

		Convey("Driver trigger request", func() {
			err := trigger(ctx, &admin.TriggerRequest{
				RunId:  runID,
				Worker: "Hello",
			}, &mockConfigProvider{}, &common.MockSwarmingAPI{}, &common.MockIsolator{})
			So(err, ShouldBeNil)
			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})
		})
	})
}
