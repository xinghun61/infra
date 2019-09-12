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
	"fmt"
	"sort"
	"testing"
	"time"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/proto/google"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/worker"
	"infra/appengine/crosskylabadmin/app/frontend/test"
)

func TestRunTaskByDUTName(t *testing.T) {
	Convey("with run repair job with DUT name", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		expectTaskCreationForDUT(tf, "task1", "host1")
		at := worker.AdminTaskForType(tf.C, fleet.TaskType_Repair)
		taskURL, err := runTaskByDUTName(tf.C, at, tf.MockSwarming, "host1")
		So(err, ShouldBeNil)
		So(taskURL, ShouldContainSubstring, "task1")
	})
}

func TestEnsureBackgroundTasks(t *testing.T) {
	Convey("with 2 known bots", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownReadyBots(tf, []string{"dut_1", "dut_2"})

		Convey("EnsureBackgroundTasks for unknown bot creates no tasks", func() {
			resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
				Type:      fleet.TaskType_Reset,
				Selectors: makeBotSelectorForDuts([]string{"dut_3"}),
			})
			So(err, ShouldBeNil)
			So(resp.BotTasks, ShouldBeEmpty)
		})
	})

	Convey("with 2 known bots", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownReadyBots(tf, []string{"dut_1", "dut_2"})

		Convey("EnsureBackgroundTasks(Reset) for known bot", func() {
			taskCount := 5
			expectListRecentTasks(tf, taskCount, "PENDING")
			for t := 0; t < taskCount; t++ {
				expectTaskCreation(tf, fmt.Sprintf("task_%d", t), "dut_1", "needs_reset", "admin_reset", 10)
			}

			resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
				Type:      fleet.TaskType_Reset,
				Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				TaskCount: int32(taskCount),
				Priority:  10,
			})

			Convey("returns bot list with requested tasks", func() {
				So(err, ShouldBeNil)
				assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": taskCount})
				for _, t := range resp.BotTasks[0].Tasks {
					So(t.Type, ShouldEqual, fleet.TaskType_Reset)
					So(t.TaskUrl, ShouldNotBeNil)
				}
			})
		})
	})

	Convey("with 2 known bots", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownReadyBots(tf, []string{"dut_1", "dut_2"})

		Convey("EnsureBackgroundTasks(Reset) for known bot with existing tasks", func() {
			oldTaskIDs := []string{"old_task_0", "old_task_1"}
			newTaskIDs := []string{"new_task_0", "new_task_1", "new_task_2"}
			taskIDs := append(oldTaskIDs, newTaskIDs...)
			requestedTaskCount := len(taskIDs)

			existingTasks := make([]*swarming.SwarmingRpcsTaskResult, 0, len(oldTaskIDs))
			for _, tid := range oldTaskIDs {
				existingTasks = append(existingTasks, &swarming.SwarmingRpcsTaskResult{
					BotId:  "bot_dut_1",
					TaskId: tid,
				})
			}
			expectListRecentTasks(tf, requestedTaskCount, "PENDING", existingTasks...)
			for _, tid := range newTaskIDs {
				expectTaskCreation(tf, tid, "", "needs_reset", "admin_reset", 10)
			}

			resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
				Type:      fleet.TaskType_Reset,
				Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				TaskCount: int32(requestedTaskCount),
				Priority:  10,
			})

			Convey("returns bot list containing existing and newly created tasks", func() {
				So(err, ShouldBeNil)
				assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": len(taskIDs)})
				taskURLs := []string{}
				for _, t := range resp.BotTasks[0].Tasks {
					taskURLs = append(taskURLs, t.TaskUrl)
				}
				assertTaskURLsForIDs(taskURLs, taskIDs)
			})

		})
	})

	Convey("with a large number of known bots", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		numDuts := 6 * clients.MaxConcurrentSwarmingCalls
		allDuts := make([]string, 0, numDuts)
		taskDuts := make([]string, 0, numDuts/2)
		perDutTaskCount := 6
		for i := 0; i < numDuts; i++ {
			allDuts = append(allDuts, fmt.Sprintf("dut_%d", i))
			if i%2 == 0 {
				taskDuts = append(taskDuts, allDuts[i])
			}
		}
		setKnownReadyBots(tf, allDuts)

		Convey("EnsureBackgroundTasks(Repair) for some of the known bots", func() {
			expectListRecentTasks(tf, perDutTaskCount, "PENDING").AnyTimes()
			for _, d := range taskDuts {
				for i := 0; i < perDutTaskCount; i++ {
					expectTaskCreation(tf, fmt.Sprintf("task_%s_%d", d, i), d, "needs_repair", "admin_repair", 0)
				}
			}

			resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
				Type:      fleet.TaskType_Repair,
				Selectors: makeBotSelectorForDuts(taskDuts),
				TaskCount: int32(perDutTaskCount),
				Priority:  9,
			})

			Convey("returns bot lists for expected duts with the right number of tasks", func() {
				So(err, ShouldBeNil)
				So(resp.BotTasks, ShouldHaveLength, len(taskDuts))
				gotDuts := []string{}
				taskCount := 0
				for _, bt := range resp.BotTasks {
					gotDuts = append(gotDuts, bt.DutId)
					taskCount += len(bt.Tasks)
				}
				assertStringSetsEqual(gotDuts, taskDuts)
				So(gotDuts, ShouldResemble, taskDuts)
				So(taskCount, ShouldEqual, perDutTaskCount*len(taskDuts))
			})
		})
	})
}

func TestTriggerRepairOnIdle(t *testing.T) {
	Convey("with one known bot with no task history", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownReadyBots(tf, []string{"dut_1"})
		expectListRecentTasks(tf, 0, "PENDING")
		expectListSortedRecentTasksForBot(tf, "dut_1")

		Convey("TriggerRepairOnIdle triggers a task for the dut", func() {
			expectTaskCreation(tf, "task_1", "dut_1", "", "admin_repair", 0)

			resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
				Selectors:    []*fleet.BotSelector{},
				IdleDuration: google.NewDuration(4),
				Priority:     20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 1})
		})
	})

	Convey("with one known bot with one task long ago", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		setKnownReadyBots(tf, []string{"dut_1"})
		expectListRecentTasks(tf, 0, "PENDING")
		expectListSortedRecentTasksForBot(tf, "dut_1", &swarming.SwarmingRpcsTaskResult{
			State:       "COMPLETED",
			CompletedTs: "2016-01-02T10:04:05.999999999",
		})

		Convey("TriggerRepairOnIdle triggers a task for the dut", func() {
			expectTaskCreation(tf, "task_1", "dut_1", "", "admin_repair", 0)

			resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
				Selectors:    []*fleet.BotSelector{},
				IdleDuration: google.NewDuration(4),
				Priority:     20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 1})
		})
	})

	Convey("with one known bot with one task in recent past", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		setKnownReadyBots(tf, []string{"dut_1"})
		expectListRecentTasks(tf, 0, "PENDING")
		expectListSortedRecentTasksForBot(tf, "dut_1", &swarming.SwarmingRpcsTaskResult{
			State:       "COMPLETED",
			CompletedTs: timeOffsetFromNowInSwarmingFormat(-5 * time.Second),
		})

		Convey("TriggerRepairOnIdle does not trigger a task", func() {
			resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
				Selectors:    []*fleet.BotSelector{},
				IdleDuration: google.NewDuration(4 * 24 * time.Hour),
				Priority:     20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 0})
		})
	})

	Convey("with one known bot with one running task", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		setKnownReadyBots(tf, []string{"dut_1"})
		expectListRecentTasks(tf, 0, "PENDING")
		expectListSortedRecentTasksForBot(tf, "dut_1", &swarming.SwarmingRpcsTaskResult{State: "RUNNING"})

		Convey("TriggerRepairOnIdle does not trigger a task", func() {
			resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
				Selectors:    []*fleet.BotSelector{},
				IdleDuration: google.NewDuration(4 * 24 * time.Hour),
				Priority:     20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 0})
		})
	})
}

func TestTriggerRepairOnRepairFailed(t *testing.T) {
	Convey("with one known bot in state ready", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownReadyBots(tf, []string{"dut_1"})

		Convey("TriggerRepairOnRepairFailed does not trigger a task for the dut", func() {
			resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
				Selectors:           []*fleet.BotSelector{},
				TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
				Priority:            20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 0})
		})
	})

	Convey("with one known bot in state repair_failed", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownBotsInState(tf, []string{"dut_1"}, "repair_failed")
		expectListRecentTasks(tf, 0, "")

		Convey("TriggerRepairOnRepairFailed triggers a task for the dut", func() {
			expectTaskCreation(tf, "task_1", "dut_1", "", "admin_repair", 0)

			resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
				Selectors:           []*fleet.BotSelector{},
				TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
				Priority:            20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 1})
		})
	})

	Convey("with one known bot in state repair_failed and a recent repair task", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownBotsInState(tf, []string{"dut_1"}, "repair_failed")
		expectListRecentTasks(tf, 0, "", &swarming.SwarmingRpcsTaskResult{
			State:       "COMPLETED",
			CompletedTs: timeOffsetFromNowInSwarmingFormat(-5 * time.Second),
		})

		Convey("TriggerRepairOnRepairFailed does not trigger a task for the dut", func() {
			resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
				Selectors:           []*fleet.BotSelector{},
				TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
				Priority:            20,
			})
			So(err, ShouldBeNil)
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 0})
		})
	})

	Convey("with one known bot in state repair_failed and a running repair task", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()
		setKnownBotsInState(tf, []string{"dut_1"}, "repair_failed")
		expectListRecentTasks(tf, 0, "", &swarming.SwarmingRpcsTaskResult{State: "RUNNING"})

		Convey("TriggerRepairOnRepairFailed does not trigger a task for the dut", func() {
			resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
				Selectors:           []*fleet.BotSelector{},
				TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
				Priority:            20,
			})
			So(err, ShouldBeNil)
			// The already running task is returned
			assertBotsWithTaskCount(resp.BotTasks, map[string]int{"dut_1": 1})
		})
	})

	// TODO(pprabhu) Add a case where the initial repair task times out1instead
	// of completing.
	// TODO(pprabhu) Add a case where the initial repair task is killed instead
	// of completing.
}

// setKnownReadyBots refreshes the internal state of the services under test so
// that the provided duts in ready state are known to the services.
func setKnownReadyBots(tf testFixture, duts []string) {
	setKnownBotsInState(tf, duts, "ready")
}

// setKnownBots refreshes the internal state of the services under test so that
// the provided duts are known to the services.
func setKnownBotsInState(tf testFixture, duts []string, state string) {
	// Clone tf so that MockSwarming interactions do not intefere with the actual
	// test.
	tf, validate := tf.CloneWithFreshMocks()
	defer validate()

	bots := make([]*swarming.SwarmingRpcsBotInfo, 0, len(duts))
	for _, d := range duts {
		bots = append(bots, test.BotForDUT(d, state, ""))
	}

	tf.MockSwarming.EXPECT().ListAliveBotsInPool(
		gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
	).AnyTimes().Return(bots, nil)
	expectDefaultPerBotRefresh(tf)

	resp, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
	So(err, ShouldBeNil)
	So(resp.DutIds, ShouldHaveLength, len(duts))
}

// expectListRecentTasks sets up expectations for checking taskCount recent
// tasks in the given state.
//
// This function returns the gomock expectation for further call chaining as
// necessary.  Pass in the zero value for an argument to not setup any
// expectation for that argument in the create task call.
//
// tasks are the Swarming tasks returned by the mock call.
func expectListRecentTasks(tf testFixture, taskCount int, state string, tasks ...*swarming.SwarmingRpcsTaskResult) *gomock.Call {
	var s interface{}
	if state == "" {
		s = gomock.Any()
	} else {
		s = gomock.Eq(state)
	}
	var tc interface{}
	if taskCount == 0 {
		tc = gomock.Any()
	} else {
		tc = gomock.Eq(taskCount)
	}
	if tasks == nil {
		tasks = make([]*swarming.SwarmingRpcsTaskResult, 0, 0)
	}
	return tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), s, tc).Return(tasks, nil)
}

// expectListSortedRecentTaskForBot sets up expectations for listing resent
// tasks for a bot for the given dut.
//
// This function returns the gomock expectation for further call chaining as
// necessary.  Pass in the zero value for an argument to not setup any
// expectation for that argument in the create task call.
//
// dutID is the ID of the Dut (not the bot) to target.  tasks are the Swarming
// tasks returned by the mock call.
func expectListSortedRecentTasksForBot(tf testFixture, dutID string, tasks ...*swarming.SwarmingRpcsTaskResult) *gomock.Call {
	var b interface{}
	if dutID == "" {
		b = gomock.Any()
	} else {
		b = fmt.Sprintf("bot_%s", dutID)
	}
	if tasks == nil {
		tasks = make([]*swarming.SwarmingRpcsTaskResult, 0, 0)
	}
	return tf.MockSwarming.EXPECT().ListSortedRecentTasksForBot(gomock.Any(), b, gomock.Any()).Return(tasks, nil)
}

// expectTaskCreation sets up the expectations for a single task creation.
//
// This function returns the gomock expectation for further call chaining as
// necessary.  Pass in the zero value for an argument to not setup any
// expectation for that argument in the create task call.
//
// taskID is the ID of the created task.
// Other arguments are expectations for the task creation call.
// dutState is the state the DUT should be in before the task, e.g.
//   "needs_reset".
// tname is task name, e.g. "admin_reset".
func expectTaskCreation(tf testFixture, taskID string, dutID string, dutState string, tname string, priority int) *gomock.Call {
	m := &createTaskArgsMatcher{
		DutID:    dutID,
		DutState: dutState,
		Priority: int64(priority),
	}
	if tname != "" {
		m.CmdSubString = fmt.Sprintf("-task-name %s", tname)
	}
	return tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), m).Return(taskID, nil)
}

// expectTaskCreationByDUTName sets up the expectations for a single task creation based on DUT name.
func expectTaskCreationForDUT(tf testFixture, taskID string, hostname string) *gomock.Call {
	m := &createTaskArgsMatcher{
		DutName: hostname,
	}
	return tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), m).Return(taskID, nil)
}

// assertBotsWithTaskCount ensures that botTasks have the expected bots and
// corresponding number of tasks.
func assertBotsWithTaskCount(botTasks []*fleet.TaskerBotTasks, exp map[string]int) {
	So(botTasks, ShouldHaveLength, len(exp))
	for _, bt := range botTasks {
		So(exp, ShouldContainKey, bt.DutId)
		So(bt.Tasks, ShouldHaveLength, exp[bt.DutId])
	}
}

// assertTaskURLsForIDs ensures that taskURLs correspond to taskIDs.
func assertTaskURLsForIDs(taskURLs, taskIDs []string) {
	So(taskURLs, ShouldHaveLength, len(taskIDs))
	sort.Strings(taskIDs)
	sort.Strings(taskURLs)
	for i := range taskIDs {
		So(taskURLs[i], ShouldContainSubstring, taskIDs[i])
	}
}

func assertStringSetsEqual(a, b []string) {
	sort.Strings(a)
	sort.Strings(b)
	So(a, ShouldResemble, b)
}
