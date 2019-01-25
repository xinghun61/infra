// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package frontend

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/appengine/gaetesting"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/frontend/internal/operations"
	"infra/qscheduler/qslib/tutils"
	swarming "infra/swarming"
)

func TestAssignTasks(t *testing.T) {
	Convey("Given a testing context with a scheduler pool", t, func() {
		ctx := gaetesting.TestingContext()
		poolID := "Pool1"
		admin := &QSchedulerAdminServerImpl{}
		sch := &QSchedulerServerImpl{}
		_, err := admin.CreateSchedulerPool(ctx, &qscheduler.CreateSchedulerPoolRequest{
			PoolId: poolID,
			Config: &qscheduler.SchedulerPoolConfig{
				Labels: []string{"label1"},
			},
		})
		So(err, ShouldBeNil)

		Convey("with an idle task that has been notified", func() {
			taskID := "Task1"
			req := swarming.NotifyTasksRequest{
				SchedulerId: poolID,
				Notifications: []*swarming.NotifyTasksItem{
					{
						Time: tutils.TimestampProto(time.Now()),
						Task: &swarming.TaskSpec{
							Id:    taskID,
							State: swarming.TaskState_PENDING,
							Slices: []*swarming.SliceSpec{
								{},
							},
						},
					},
				},
			}
			_, err := sch.NotifyTasks(ctx, &req)
			So(err, ShouldBeNil)

			Convey("when AssignTasks is called with an idle bot", func() {
				botID := "Bot1"
				req := swarming.AssignTasksRequest{
					SchedulerId: poolID,
					Time:        tutils.TimestampProto(time.Now()),
					IdleBots: []*swarming.IdleBot{
						{BotId: botID, Dimensions: []string{"label1"}},
					},
				}
				resp, err := sch.AssignTasks(ctx, &req)
				Convey("then the task is assigned to the bot.", func() {
					So(err, ShouldBeNil)
					So(resp.Assignments, ShouldHaveLength, 1)
					So(resp.Assignments[0].BotId, ShouldEqual, botID)
					So(resp.Assignments[0].TaskId, ShouldEqual, taskID)
				})
			})
		})

		Convey("when AssignTasks is called with an idle bot that doesn't have needed dimensions", func() {
			botID := "Bot1"
			req := swarming.AssignTasksRequest{
				SchedulerId: poolID,
				Time:        tutils.TimestampProto(time.Now()),
				IdleBots: []*swarming.IdleBot{
					{BotId: botID},
				},
			}
			resp, err := sch.AssignTasks(ctx, &req)
			Convey("then an error is returned.", func() {
				So(resp, ShouldBeNil)
				So(err, ShouldNotBeNil)
				So(err.Error(), ShouldContainSubstring, "does not have all scheduler dimensions")
			})
		})
	})
}

// TODO(akeshet): Move this to whichever package GetProvisionableLabels ends up in.
func TestGetProvisionableLabels(t *testing.T) {
	cases := []struct {
		caseName        string
		sliceDimensions [][]string
		expected        []string
		errorExpected   bool
	}{
		// 0 slices should return an error.
		{
			"Given a task notification with 0 slices",
			nil,
			nil,
			true,
		},
		// 1 slice should return an empty dimension list.
		{
			"Given a task notification with 1 slice",
			[][]string{{"dimension1"}},
			[]string{},
			false,
		},
		// 2 slices where second one is not a subset of first should return an error.
		{
			"Given a task notification with 2 slices, where second slice dimensions are not subset of first",
			[][]string{
				{"common dimension"},
				{"common dimensions", "erroneous extra dimension"},
			},
			nil,
			true,
		},
		// 2 slices with well formed dimensions should return provisionable labels.
		{
			"Given a task notification with 2 well formed slices",
			[][]string{
				{"common dimension", "provisionable label 1", "provisionable label 2"},
				{"common dimension"},
			},
			[]string{"provisionable label 1", "provisionable label 2"},
			false,
		},
		// 3 slices should return an error.
		{
			"Given a task notification with 3 slices",
			[][]string{{}, {}, {}},
			nil,
			true,
		},
	}
	for _, c := range cases {
		Convey(c.caseName, t, func() {
			n := &swarming.NotifyTasksItem{}
			n.Task = &swarming.TaskSpec{}
			for _, dims := range c.sliceDimensions {
				newSlice := &swarming.SliceSpec{}
				newSlice.Dimensions = dims
				n.Task.Slices = append(n.Task.Slices, newSlice)
			}
			Convey("when getProvisionableLabels is called, it returns expected value and error.", func() {
				got, gotError := operations.ProvisionableLabels(n)
				So(got, ShouldResemble, c.expected)
				if c.errorExpected {
					So(gotError, ShouldNotBeNil)
				} else {
					So(gotError, ShouldBeNil)
				}
			})
		})
	}
}

func TestGetAccountId(t *testing.T) {
	cases := []struct {
		name            string
		tags            []string
		expectedAccount string
		errorExpected   bool
	}{
		{
			"nil tags",
			nil,
			"",
			false,
		},
		{
			"no relevant tags",
			[]string{"foo:1", "foo:2"},
			"",
			false,
		},
		{
			"one account tag",
			[]string{"qs_account:foo", "foo:2"},
			"foo",
			false,
		},
		{
			"two account tags",
			[]string{"qs_account:foo", "qs_account:bar"},
			"",
			true,
		},
	}
	for _, c := range cases {
		Convey("When a task has "+c.name, t, func() {
			Convey("then getAccountID returns the correct value / error.", func() {
				i := &swarming.NotifyTasksItem{Task: &swarming.TaskSpec{Tags: c.tags}}
				a, err := operations.GetAccountID(i)
				So(a, ShouldEqual, c.expectedAccount)
				if c.errorExpected {
					So(err, ShouldNotBeNil)
				} else {
					So(err, ShouldBeNil)
				}
			})
		})
	}
}
