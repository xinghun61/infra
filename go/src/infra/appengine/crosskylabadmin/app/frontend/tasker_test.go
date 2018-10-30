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
	"strings"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/proto/google"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
)

func TestEnsureBackgroundTasks(t *testing.T) {
	Convey("In testing context", t, FailureHalts, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()

		Convey("with 2 known bots", func() {
			setKnownBots(tf.C, tf.FakeSwarming, []string{"dut_1", "dut_2"})

			Reset(func() {
				tf.FakeSwarming.ResetTasks()
			})

			Convey("EnsureBackgroundTasks for unknown bot creates no tasks", func() {
				resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
					Type:      fleet.TaskType_Reset,
					Selectors: makeBotSelectorForDuts([]string{"dut_3"}),
				})
				So(err, ShouldBeNil)
				So(resp.BotTasks, ShouldBeEmpty)
			})

			taskURLFirst := []string{}
			Convey("EnsureBackgroundTasks(Reset) for known bot", func() {
				resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
					Type:      fleet.TaskType_Reset,
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
					TaskCount: 5,
					Priority:  10,
				})

				So(err, ShouldBeNil)
				Convey("creates expected swarming tasks", func() {
					So(tf.FakeSwarming.taskArgs, ShouldHaveLength, 5)
					for _, ta := range tf.FakeSwarming.taskArgs {
						So(ta.DutID, ShouldEqual, "dut_1")
						So(ta.DutState, ShouldEqual, "needs_reset")
						So(ta.Priority, ShouldEqual, 10)

						cmd := strings.Join(ta.Cmd, " ")
						So(cmd, ShouldContainSubstring, "-task-name admin_reset")
					}

				})
				Convey("returns bot list with requested tasks", func() {
					So(resp.BotTasks, ShouldHaveLength, 1)
					botTasks := resp.BotTasks[0]
					So(botTasks.DutId, ShouldEqual, "dut_1")
					So(botTasks.Tasks, ShouldHaveLength, 5)
					for _, t := range botTasks.Tasks {
						So(t.Type, ShouldEqual, fleet.TaskType_Reset)
						So(t.TaskUrl, ShouldNotBeNil)
						taskURLFirst = append(taskURLFirst, t.TaskUrl)
					}
				})

				Convey("then another EnsureBackgroundTasks(Reset) with more tasks requested", func() {
					resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
						Type:      fleet.TaskType_Reset,
						Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
						TaskCount: 7,
						Priority:  10,
					})

					So(err, ShouldBeNil)
					Convey("creates remaining swarming tasks", func() {
						// This includes the 5 created earlier.
						So(tf.FakeSwarming.taskArgs, ShouldHaveLength, 7)
					})
					Convey("returns bot list containing tasks created earlier and the new tasks", func() {
						So(resp.BotTasks, ShouldHaveLength, 1)
						botTasks := resp.BotTasks[0]
						So(botTasks.DutId, ShouldEqual, "dut_1")
						So(botTasks.Tasks, ShouldHaveLength, 7)
						taskURLSecond := []string{}
						for _, t := range botTasks.Tasks {
							taskURLSecond = append(taskURLSecond, t.TaskUrl)
						}
						for _, t := range taskURLFirst {
							So(t, ShouldBeIn, taskURLSecond)
						}
					})
				})
			})
		})

		Convey("with a large number of known bots", func() {
			numDuts := 6 * clients.MaxConcurrentSwarmingCalls
			allDuts := make([]string, 0, numDuts)
			taskDuts := make([]string, 0, numDuts/2)
			for i := 0; i < numDuts; i++ {
				allDuts = append(allDuts, fmt.Sprintf("dut_%d", i))
				if i%2 == 0 {
					taskDuts = append(taskDuts, allDuts[i])
				}
			}
			setKnownBots(tf.C, tf.FakeSwarming, allDuts)

			Convey("EnsureBackgroundTasks(Repair) for some of the known bots", func() {
				resp, err := tf.Tasker.EnsureBackgroundTasks(tf.C, &fleet.EnsureBackgroundTasksRequest{
					Type:      fleet.TaskType_Repair,
					Selectors: makeBotSelectorForDuts(taskDuts),
					TaskCount: 6,
					Priority:  9,
				})

				So(err, ShouldBeNil)
				Convey("creates expected swarming tasks", func() {
					So(tf.FakeSwarming.taskArgs, ShouldHaveLength, 6*len(taskDuts))
					gotDuts := map[string]int{}
					for _, ta := range tf.FakeSwarming.taskArgs {
						So(ta.DutState, ShouldEqual, "needs_repair")
						So(ta.Priority, ShouldEqual, 9)
						gotDuts[ta.DutID] = gotDuts[ta.DutID] + 1
						cmd := strings.Join(ta.Cmd, " ")
						So(cmd, ShouldContainSubstring, "-task-name admin_repair")
					}
					So(gotDuts, ShouldHaveLength, len(taskDuts))
					for d, c := range gotDuts {
						So(d, ShouldBeIn, taskDuts)
						So(c, ShouldEqual, 6)
					}
				})
				Convey("returns bot list with requested tasks", func() {
					So(resp.BotTasks, ShouldHaveLength, len(taskDuts))
					gotDuts := map[string]bool{}
					for _, bt := range resp.BotTasks {
						So(bt.Tasks, ShouldHaveLength, 6)
						for _, t := range bt.Tasks {
							So(t.Type, ShouldEqual, fleet.TaskType_Repair)
							So(t.TaskUrl, ShouldNotBeNil)
						}
						So(bt.DutId, ShouldBeIn, taskDuts)
						gotDuts[bt.DutId] = true
					}
					So(gotDuts, ShouldHaveLength, len(taskDuts))
				})
			})
		})
	})
}

func TestTriggerRepairOnIdle(t *testing.T) {
	Convey("In testing context", t, FailureHalts, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()

		Convey("with one known bot", func() {
			setKnownBots(tf.C, tf.FakeSwarming, []string{"dut_1"})

			Reset(func() {
				tf.FakeSwarming.ResetTasks()
			})

			Convey("TriggerRepairOnIdle triggers a task for the dut", func() {
				resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
					Selectors:    []*fleet.BotSelector{},
					IdleDuration: google.NewDuration(4),
					Priority:     20,
				})
				So(err, ShouldBeNil)
				So(resp.BotTasks, ShouldHaveLength, 1)

				botTask := resp.BotTasks[0]
				So(botTask.DutId, ShouldEqual, "dut_1")
				So(botTask.Tasks, ShouldHaveLength, 1)

				Convey("then TriggerRepairOnIdle returns the already scheduled task", func() {
					taskURL := botTask.Tasks[0].TaskUrl
					resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
						Selectors:    []*fleet.BotSelector{},
						IdleDuration: google.NewDuration(4),
						Priority:     20,
					})
					So(err, ShouldBeNil)
					So(resp.BotTasks, ShouldHaveLength, 1)

					botTask := resp.BotTasks[0]
					So(botTask.DutId, ShouldEqual, "dut_1")
					So(botTask.Tasks, ShouldHaveLength, 1)
					So(botTask.Tasks[0].TaskUrl, ShouldEqual, taskURL)
				})
			})

			Convey("and one task in the long past", func() {
				tf.FakeSwarming.botTasks["bot_dut_1"] = []*swarming.SwarmingRpcsTaskResult{
					{
						State:       "COMPLETED",
						CompletedTs: "2016-01-02T10:04:05.999999999",
					},
				}
				_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
				So(err, ShouldBeNil)

				Convey("TriggerRepairOnIdle triggers a task for the dut", func() {
					resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
						Selectors:    []*fleet.BotSelector{},
						IdleDuration: google.NewDuration(4),
						Priority:     20,
					})
					So(err, ShouldBeNil)
					So(resp.BotTasks, ShouldHaveLength, 1)

					botTask := resp.BotTasks[0]
					So(botTask.DutId, ShouldEqual, "dut_1")
					So(botTask.Tasks, ShouldHaveLength, 1)
				})
			})

			Convey("and one task in recent past", func() {
				yyyy, mm, dd := time.Now().Date()
				tf.FakeSwarming.botTasks["bot_dut_1"] = []*swarming.SwarmingRpcsTaskResult{
					{
						State:       "COMPLETED",
						CompletedTs: fmt.Sprintf("%04d-%02d-%02dT00:00:00.00000000", yyyy, mm, dd),
					},
				}
				_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
				So(err, ShouldBeNil)

				Convey("TriggerRepairOnIdle does not trigger a task", func() {
					resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
						Selectors:    []*fleet.BotSelector{},
						IdleDuration: google.NewDuration(4 * 24 * time.Hour),
						Priority:     20,
					})
					So(err, ShouldBeNil)
					So(resp.BotTasks, ShouldHaveLength, 1)

					botTask := resp.BotTasks[0]
					So(botTask.Tasks, ShouldHaveLength, 0)
				})
			})

			Convey("and one running task", func() {
				tf.FakeSwarming.botTasks["bot_dut_1"] = []*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
				}
				_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
				So(err, ShouldBeNil)

				Convey("TriggerRepairOnIdle does not trigger a task", func() {
					resp, err := tf.Tasker.TriggerRepairOnIdle(tf.C, &fleet.TriggerRepairOnIdleRequest{
						Selectors:    []*fleet.BotSelector{},
						IdleDuration: google.NewDuration(4 * 24 * time.Hour),
						Priority:     20,
					})
					So(err, ShouldBeNil)
					So(resp.BotTasks, ShouldHaveLength, 1)

					botTask := resp.BotTasks[0]
					So(botTask.Tasks, ShouldHaveLength, 0)
				})
			})
		})
	})
}

func TestTriggerRepairOnRepairFailed(t *testing.T) {
	Convey("In testing context", t, FailureHalts, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()

		Convey("with one known bot in state ready", func() {
			setKnownBots(tf.C, tf.FakeSwarming, []string{"dut_1"})

			Convey("TriggerRepairOnRepairFailed does not trigger a task for the dut", func() {
				resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
					Selectors:           []*fleet.BotSelector{},
					TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
					Priority:            20,
				})
				So(err, ShouldBeNil)
				So(resp.BotTasks, ShouldHaveLength, 1)

				botTask := resp.BotTasks[0]
				So(botTask.Tasks, ShouldHaveLength, 0)
			})
		})

		Convey("with one known bot in state repair_failed", func() {
			tf.FakeSwarming.botInfos = map[string]*swarming.SwarmingRpcsBotInfo{
				"bot_dut_1": {
					BotId: "bot_dut_1",
					Dimensions: []*swarming.SwarmingRpcsStringListPair{
						{
							Key:   "dut_id",
							Value: []string{"dut_1"},
						},
						{
							Key:   "dut_state",
							Value: []string{"repair_failed"},
						},
					},
				},
			}
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)

			Convey("TriggerRepairOnRepairFailed triggers a task for the dut", func() {
				resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
					Selectors:           []*fleet.BotSelector{},
					TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
					Priority:            20,
				})
				So(err, ShouldBeNil)
				So(resp.BotTasks, ShouldHaveLength, 1)

				botTask := resp.BotTasks[0]
				So(botTask.Tasks, ShouldHaveLength, 1)
				taskURL := botTask.Tasks[0].TaskUrl

				Convey("then TriggerRepairOnRepairFailed returns the same task", func() {
					resp, err := tf.Tasker.TriggerRepairOnRepairFailed(tf.C, &fleet.TriggerRepairOnRepairFailedRequest{
						Selectors:           []*fleet.BotSelector{},
						TimeSinceLastRepair: google.NewDuration(24 * time.Hour),
						Priority:            20,
					})
					So(err, ShouldBeNil)
					So(resp.BotTasks, ShouldHaveLength, 1)

					botTask := resp.BotTasks[0]
					So(botTask.Tasks, ShouldHaveLength, 1)
					So(botTask.Tasks[0].TaskUrl, ShouldEqual, taskURL)
				})

				// TODO(pprabhu) Add a case where the intial repair task has completed,
				// but is within TimeSinceLastRepair. No new tasks should be created,
				// and no task should be returned.

				// TODO(pprabhu) Add a case where the initial repair task times out instead of completing.

				// TODO(pprabhu) Add a case where the initial repair task is killed instead of completing.
			})
		})
	})
}

func setKnownBots(c context.Context, fsc *fakeSwarmingClient, duts []string) {
	fsc.setAvailableDutIDs(duts)
	server := TrackerServerImpl{
		ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return fsc, nil
		},
	}
	resp, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{})
	So(err, ShouldBeNil)
	So(resp.DutIds, ShouldHaveLength, len(duts))
}
