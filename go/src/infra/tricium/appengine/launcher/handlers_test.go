// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package launcher

import (
	"testing"

	"golang.org/x/net/context"

	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"

	. "github.com/smartystreets/goconvey/convey"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/pipeline"
	trit "infra/tricium/appengine/common/testing"
)

type mockConfigProvider struct {
}

func (*mockConfigProvider) readConfig(c context.Context, project string) (*admin.Workflow, error) {
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

func TestLaunchRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		lr := &pipeline.LaunchRequest{
			RunID:   123456789,
			Project: "test-project",
			GitRef:  "ref/test",
			Paths: []string{
				"README.md",
				"README2.md",
			},
		}
		Convey("Launch request", func() {
			err := launch(ctx, lr, &mockConfigProvider{})
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Stores workflow config", func() {
				wf := &common.Entity{
					ID:   lr.RunID,
					Kind: "Workflow",
				}
				err := ds.Get(ctx, wf)
				So(err, ShouldBeNil)
			})

			Convey("Enqueues driver requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 2)
			})
		})
	})
}
