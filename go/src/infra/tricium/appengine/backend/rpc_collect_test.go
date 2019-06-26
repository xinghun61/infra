// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/triciumtest"
)

// Mock Swarming API that returns a canned task result.
type mockSwarming struct {
	State common.ResultState
}

func (mockSwarming) Trigger(c context.Context, params *common.TriggerParameters) (*common.TriggerResult, error) {
	return &common.TriggerResult{TaskID: "mocktaskid"}, nil
}
func (m mockSwarming) Collect(c context.Context, params *common.CollectParameters) (*common.CollectResult, error) {
	return &common.CollectResult{
		State:              m.State,
		IsolatedOutputHash: "mockisolatedoutput",
	}, nil
}

func TestCollectRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()
		runID := int64(123456789)

		workflowProvider := &mockWorkflowProvider{
			Workflow: &admin.Workflow{
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
			},
		}

		Convey("Driver collect request for worker with successors", func() {
			err := collect(ctx, &admin.CollectRequest{
				RunId:  runID,
				Worker: "World",
			}, workflowProvider, common.MockTaskServerAPI, common.MockTaskServerAPI, common.MockIsolator)
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Enqueues driver request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 1)
			})
		})

		Convey("Failing collect request for worker with successors", func() {
			err := collect(ctx, &admin.CollectRequest{
				RunId:  runID,
				Worker: "World",
			}, workflowProvider, mockSwarming{
				State: common.Failure,
			}, common.MockTaskServerAPI, common.MockIsolator)
			So(err, ShouldBeNil)

			Convey("Enqueues track requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 2)
			})

			Convey("Enqueues no driver requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 0)
			})
		})

		Convey("Driver collect request for worker without successors", func() {
			err := collect(ctx, &admin.CollectRequest{
				RunId:  runID,
				Worker: "Hello",
			}, workflowProvider, common.MockTaskServerAPI, common.MockTaskServerAPI, common.MockIsolator)
			So(err, ShouldBeNil)

			Convey("Enqueues track request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.TrackerQueue]), ShouldEqual, 1)
			})

			Convey("Enqueues no driver request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 0)
			})
		})

		Convey("Driver collect request for incomplete worker without successors", func() {
			err := collect(ctx, &admin.CollectRequest{
				RunId:  runID,
				Worker: "Hello",
			}, workflowProvider, mockSwarming{
				State: common.Pending,
			}, common.MockTaskServerAPI, common.MockIsolator)
			So(err, ShouldBeNil)

			Convey("Re-enqueues the a driver (collect) request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]), ShouldEqual, 1)
				task := tq.GetTestable(ctx).GetScheduledTasks()[common.DriverQueue]["5023444679101355902"]
				So(task.ETA, ShouldEqual, clock.Now(ctx).Add(30*time.Second))
			})
		})
	})
}

func TestValidateCollectRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("A request with run ID and worker name is valid", func() {
			So(validateCollectRequest(&admin.CollectRequest{
				RunId:             int64(1234),
				Worker:            "Hello",
				IsolatedInputHash: "53df47e7dcfecdafb25030cc9fabc2c18f6d9e82",
			}), ShouldBeNil)

			// Isolated input hash is optional, and may not be present
			// if the task was aborted or failed in some other way.
			So(validateCollectRequest(&admin.CollectRequest{
				RunId:  int64(1234),
				Worker: "Hello",
			}), ShouldBeNil)
		})

		Convey("A request missing either run ID or worker name is not valid", func() {
			So(validateCollectRequest(&admin.CollectRequest{
				Worker: "Hello",
			}), ShouldNotBeNil)
			So(validateCollectRequest(&admin.CollectRequest{
				RunId: int64(1234),
			}), ShouldNotBeNil)
		})
	})
}
