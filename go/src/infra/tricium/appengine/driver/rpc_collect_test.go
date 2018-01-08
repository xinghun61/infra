// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package driver

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	tq "go.chromium.org/gae/service/taskqueue"

	"golang.org/x/net/context"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

type mockSwarmingFailure struct {
}

func (mockSwarmingFailure) Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string) (string, error) {
	return "mockmockmock", nil
}
func (mockSwarmingFailure) Collect(c context.Context, serverURL string, taskID string) (string, int64, error) {
	return "", 1, nil
}

func TestCollectRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()
		runID := int64(123456789)

		Convey("Driver collect request for worker with successors", func() {
			err := collect(ctx, &admin.CollectRequest{
				RunId:  runID,
				Worker: "World",
			}, mockWorkflowProvider{}, common.MockSwarmingAPI, common.MockIsolator)
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
			}, mockWorkflowProvider{}, &mockSwarmingFailure{}, common.MockIsolator)
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
			}, mockWorkflowProvider{}, common.MockSwarmingAPI, common.MockIsolator)
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
