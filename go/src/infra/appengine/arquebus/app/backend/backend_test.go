// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"

	"infra/appengine/arquebus/app/backend/model"
	"infra/monorailv2/api/api_proto"
)

func TestBackend(t *testing.T) {
	t.Parallel()
	assignerID := "test-assigner"

	Convey("scheduleAssignerTaskHandler", t, func() {
		c := createTestContextWithTQ()

		// create a sample assigner with tasks.
		createAssigner(c, assignerID)
		tasks := triggerScheduleTaskHandler(c, assignerID)
		So(tasks, ShouldNotBeNil)

		Convey("works", func() {
			for _, task := range tasks {
				So(task.Status, ShouldEqual, model.TaskStatus_Scheduled)
			}
		})

		Convey("doesn't schedule new tasks for a drained assigner.", func() {
			// TODO(crbug/967519): implement me.
		})
	})

	Convey("runAssignerTaskHandler", t, func() {
		c := createTestContextWithTQ()
		createAssigner(c, assignerID)
		tasks := triggerScheduleTaskHandler(c, assignerID)
		So(tasks, ShouldNotBeNil)

		Convey("works", func() {
			mockListIssues(
				c, &monorail.Issue{ProjectName: "test", LocalId: 123},
			)

			for _, task := range tasks {
				So(task.Status, ShouldEqual, model.TaskStatus_Scheduled)
				task := triggerRunTaskHandler(c, assignerID, task.ID)

				So(task.Status, ShouldEqual, model.TaskStatus_Succeeded)
				So(task.Started.IsZero(), ShouldBeFalse)
				So(task.Ended.IsZero(), ShouldBeFalse)
			}
		})

		Convey("cancelling stale tasks.", func() {
			// make one stale schedule
			task := tasks[0]
			task.ExpectedStart = task.ExpectedStart.Add(-10 * time.Hour)
			So(task.ExpectedStart.Before(clock.Now(c).UTC()), ShouldBeTrue)
			So(task.Status, ShouldEqual, model.TaskStatus_Scheduled)
			So(datastore.Put(c, task), ShouldBeNil)

			// It should be marked as cancelled after runTaskHandler().
			processedTask := triggerRunTaskHandler(c, assignerID, task.ID)
			So(processedTask.Status, ShouldEqual, model.TaskStatus_Cancelled)
			So(processedTask.Started.IsZero(), ShouldBeFalse)
			So(processedTask.Ended.IsZero(), ShouldBeFalse)
		})

		Convey("task status is kept as original, if not scheduled.", func() {
			// make one with an invalid status. TaskStatus_Scheduled is the
			// the only status valid for runTaskHandler()
			task := tasks[0]
			task.Status = model.TaskStatus_Failed
			task.Started = time.Date(2000, 1, 1, 2, 3, 4, 0, time.UTC)
			task.Ended = task.Started.AddDate(0, 1, 2)
			So(datastore.Put(c, task), ShouldBeNil)

			// The task should stay the same after runTaskHandler().
			processedTask := triggerRunTaskHandler(c, assignerID, task.ID)
			So(processedTask.Status, ShouldEqual, task.Status)
			So(processedTask.Started, ShouldEqual, task.Started)
			So(processedTask.Ended, ShouldEqual, task.Ended)
		})

		Convey("cancelling tasks, if the assigner has been drained.", func() {
			// TODO(crbug/967519): implement me.
		})
	})
}
