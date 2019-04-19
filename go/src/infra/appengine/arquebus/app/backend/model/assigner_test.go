// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"context"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"infra/appengine/arquebus/app/util"
)

func TestUpdateAssigners(t *testing.T) {
	t.Parallel()

	Convey("UpdateAssigners", t, func() {
		c := util.CreateTestContext()
		rev1, rev2, rev3 := "abc", "def", "ghi"

		// Ensure empty now.
		ds.GetTestable(c).CatchupIndexes()
		assigners, err := GetAllAssigners(c)
		So(err, ShouldBeNil)
		So(assigners, ShouldBeNil)

		Convey("Creates a new Assigner", func() {
			assigners := updateAndGetAllAssigners(
				c, rev1, createConfig("test-a"))
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, "test-a")
		})

		Convey("Updates an existing Assigner", func() {
			assigners := updateAndGetAllAssigners(c, rev1, createConfig("test-a"))
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, "test-a")

			// increase the interval just to check the Assigner
			// has been updated or not.
			cfg := createConfig("test-a")
			original := cfg.Interval.Seconds
			cfg.Interval.Seconds = original + 1
			changed := time.Duration(original+1) * time.Second

			Convey("With a new revision", func() {
				assigners := updateAndGetAllAssigners(c, rev2, cfg)
				So(len(assigners), ShouldEqual, 1)
				So(assigners[0].Interval, ShouldEqual, changed)
			})

			Convey("With the same new revision", func() {
				assigners := updateAndGetAllAssigners(c, rev1, cfg)
				So(len(assigners), ShouldEqual, 1)
				du := time.Duration(original) * time.Second
				So(assigners[0].Interval, ShouldEqual, du)
			})
		})

		Convey("Marks as removed if config removed", func() {
			// create
			id := "test-a"
			cfg := createConfig(id)
			assigners := updateAndGetAllAssigners(c, rev1, cfg)
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, id)

			// remove
			assigners = updateAndGetAllAssigners(c, rev2)
			So(assigners, ShouldBeNil)

			// put it back
			assigners = updateAndGetAllAssigners(c, rev3, cfg)
			So(assigners[0].ID, ShouldEqual, id)
		})
	})
}

func TestEnsureScheduledTasks(t *testing.T) {
	t.Parallel()
	var err error

	Convey("EnsureScheduledTasks", t, func() {
		c := util.CreateTestContext()
		cl := testclock.New(time.Unix(testclock.TestTimeUTC.Unix(), 0).UTC())
		c = clock.Set(c, cl)

		assigner := updateAndGetAllAssigners(c, "rev1", createConfig("a"))[0]
		So(assigner.IsDrained, ShouldEqual, false)

		// helpers to make the body of unit tests smaller.
		ensureScheduledTasks := func(c context.Context) (tasks []*Task) {
			err = ds.RunInTransaction(c, func(c context.Context) error {
				tasks, err = EnsureScheduledTasks(c, assigner.ID)
				return err
			}, &ds.TransactionOptions{})
			So(err, ShouldBeNil)
			return tasks
		}
		getTasks := func(c context.Context, n int32) []*Task {
			tasks, err := GetTasks(c, assigner, n, false)
			So(err, ShouldBeNil)
			return tasks
		}

		Convey("if assigner_interval == scheduler_interval", func() {
			So(assigner.Interval, ShouldEqual, scheduleAssignerCronInterval)
			tasks := ensureScheduledTasks(c)
			// Then, it should just create 1 task.
			So(len(tasks), ShouldEqual, 1)

			Convey("with completed tasks only", func() {
				// mark the task as completed.
				tasks[0].Status = TaskStatus_Succeeded
				So(ds.Put(c, tasks[0]), ShouldBeNil)

				// advance the current timestamp by the interval and run the
				// scheduler logic.
				cl.Add(assigner.Interval)
				ensureScheduledTasks(c)

				// getTasks() returns Tasks in the order of desc ExpectedStart.
				tasks = getTasks(c, 100)
				So(len(tasks), ShouldEqual, 2)
				newTask, existingTask := tasks[0], tasks[1]

				So(newTask.Status, ShouldEqual, TaskStatus_Scheduled)
				So(newTask.ExpectedStart, ShouldResemble, cl.Now().Add(assigner.Interval))
				So(existingTask.Status, ShouldEqual, TaskStatus_Succeeded)
			})

			Convey("with a scheduled task", func() {
				cl.Add(time.Second)
				// There shouldn't be any new Tasks created.
				So(ensureScheduledTasks(c), ShouldBeNil)
				tasks = getTasks(c, 100)
				So(len(tasks), ShouldEqual, 1)
			})

			Convey("with a stale, scheduled task", func() {
				// Advance the time.
				cl.Add(assigner.Interval)
				// Now, the existing task should be considered stale.
				// A new task should be created by the scheduler.
				So(len(ensureScheduledTasks(c)), ShouldEqual, 1)

				// getTasks() returns Tasks in the order of desc ExpectedStart.
				tasks = getTasks(c, 100)
				newTask, existingTask := tasks[0], tasks[1]

				// Verify the existing Task is still marked as Scheduled.
				So(existingTask.Status, ShouldEqual, TaskStatus_Scheduled)
				So(newTask.Status, ShouldEqual, TaskStatus_Scheduled)
				So(newTask.ExpectedStart, ShouldEqual, cl.Now().Add(assigner.Interval))
			})
		})

		Convey("if assigner_interval > scheduler_interval", func() {
			// This is the case where the next scheduler run comes before
			// latestSchedule + Assigner.Interval. In theory, it's not
			// necessary to schedule a Task immediately because there will be
			// another chance for the scheduler to create a new Task
			// for the next ETA. However, EnsureScheduledTasks() ensures
			// that there is at least one Task always, and, therefore, it
			// should create a new Task regardless.
			assigner.Interval = scheduleAssignerCronInterval * 2
			now := cl.Now().UTC()
			So(ds.Put(c, assigner), ShouldBeNil)

			// This should create a new one.
			tasks := ensureScheduledTasks(c)
			So(len(tasks), ShouldEqual, 1)
			newTask := tasks[0]

			So(
				newTask.ExpectedStart, ShouldEqual,
				now.Add(scheduleAssignerCronInterval*2),
			)
		})

		Convey("if assigner_interval < scheduler_interval", func() {
			// EnsureScheduledTasks() should create an enough number of Task(s)
			// to cover all the period until the next scheduler run.
			assigner.Interval = scheduleAssignerCronInterval / 4
			now := cl.Now().UTC()
			So(ds.Put(c, assigner), ShouldBeNil)
			tasks := ensureScheduledTasks(c)
			So(len(tasks), ShouldEqual, 4)
			for i := 0; i < 4; i++ {
				// each should assigner.Interval further away from the previous
				// schedule.
				start := now.Add(assigner.Interval * time.Duration(i+1))
				So(tasks[i].ExpectedStart, ShouldEqual, start)
			}
		})

		Convey("with drained Assigner", func() {
			// Drain it.
			assigner.IsDrained = true
			So(ds.Put(c, assigner), ShouldBeNil)
			So(ensureScheduledTasks(c), ShouldBeNil)
		})
	})
}
