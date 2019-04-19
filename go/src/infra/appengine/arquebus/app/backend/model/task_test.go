// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/appengine/arquebus/app/util"
)

func TestGetTasks(t *testing.T) {
	t.Parallel()
	now := testclock.TestTimeUTC

	Convey("GetTasks", t, func() {
		c := util.CreateTestContext()

		// create sample tasks.
		assigner := updateAndGetAllAssigners(c, "rev-1", createConfig("a"))[0]
		times := []time.Time{now, now.Add(assigner.Interval)}
		createTasks(c, assigner, TaskStatus_Scheduled, times...)

		Convey("working", func() {
			tasks, err := GetTasks(c, assigner, int32(len(times)), false)
			So(err, ShouldBeNil)
			So(len(tasks), ShouldEqual, len(times))
			for i := 0; i < len(times); i++ {
				So(tasks[i].ExpectedStart.Unix(), ShouldEqual,
					times[len(times)-i-1].Unix())
			}
		})

		Convey("with NoopSuccess", func() {
			tasks, err := GetTasks(c, assigner, int32(len(times)), false)
			So(err, ShouldBeNil)
			So(len(tasks), ShouldEqual, len(times))

			tasks[0].WasNoopSuccess = true
			tasks[0].Status = TaskStatus_Succeeded
			So(datastore.Put(c, tasks), ShouldBeNil)

			tasks, err = GetTasks(c, assigner, int32(len(times)), false)
			So(err, ShouldBeNil)
			So(len(tasks), ShouldEqual, len(times)-1)

			tasks, err = GetTasks(c, assigner, int32(len(times)), true)
			So(err, ShouldBeNil)
			So(len(tasks), ShouldEqual, len(times))
		})
	})
}
