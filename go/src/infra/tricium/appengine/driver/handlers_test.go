// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"testing"

	"golang.org/x/net/context"

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

func (*mockConfigProvider) readConfig(c context.Context, runID int64) (*admin.Workflow, error) {
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

func TestDriverRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)

		Convey("Driver trigger request", func() {
			dr := &pipeline.DriverRequest{
				Kind:   pipeline.DriverTrigger,
				RunID:  runID,
				Worker: "Hello",
			}
			err := drive(ctx, dr, &mockConfigProvider{})
			So(err, ShouldBeNil)
			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})
		})

		Convey("Driver collect request for worker with successors", func() {
			dr := &pipeline.DriverRequest{
				Kind:   pipeline.DriverCollect,
				RunID:  runID,
				Worker: "World",
			}
			err := drive(ctx, dr, &mockConfigProvider{})
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Enqueues driver request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 1)
			})
		})

		Convey("Driver collect request for worker without successors", func() {
			dr := &pipeline.DriverRequest{
				Kind:   pipeline.DriverCollect,
				RunID:  runID,
				Worker: "Hello",
			}
			err := drive(ctx, dr, &mockConfigProvider{})
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Enqueues no driver request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 0)
			})
		})
	})
}
