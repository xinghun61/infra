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
	"testing"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
)

// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the fields of returned bots.
func TestRefreshAndSummarizeNoBotsAvailable(t *testing.T) {
	Convey("with no swarming duts available", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{})

		Convey("refresh without filter refreshes no duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldBeEmpty)

		})

		Convey("refresh with empty filter refreshes no duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{}),
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldBeEmpty)
		})

		Convey("refresh with non-empty filter refreshes no duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldBeEmpty)

			Convey("then summarize without filter summarizes no duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldBeEmpty)
			})

			Convey("then summarize with empty filter summarizes no duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldBeEmpty)
			})

			Convey("then summarize with non-empty filter summarizes no duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldBeEmpty)
			})
		})
	})
}

// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the fields of returned bots.
func TestRefreshAndSummarizeOneBotAvailable(t *testing.T) {
	Convey("with a single dut available", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{"dut_1"})

		Convey("refresh filtering to available dut refreshes that dut", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
			})

			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 1)
			So(refreshed.DutIds, ShouldContain, "dut_1")
		})

		Convey("refresh filtering to unknown dut refreshes no duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{"dut_2"}),
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldBeEmpty)
		})

		Convey("refresh without filter refreshes that dut", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 1)
			So(refreshed.DutIds, ShouldContain, "dut_1")

			Convey("then summarize without filter summarizes that dut", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
				So(err, ShouldBeNil)

				duts := extractSummarizedDutIDs(summarized)
				So(duts, ShouldHaveLength, 1)
				So(duts, ShouldContain, "dut_1")
			})

			Convey("then summarize with empty filter summarizes not duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: []*fleet.BotSelector{{}},
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldBeEmpty)
			})

			Convey("then summarize filtering to available dut summarizes that dut", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				})
				So(err, ShouldBeNil)

				duts := extractSummarizedDutIDs(summarized)
				So(duts, ShouldHaveLength, 1)
				So(duts, ShouldContain, "dut_1")
			})

			Convey("then summarize filtering to unknown dut summarizes no duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_2"}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldBeEmpty)
			})
		})
	})
}

// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the fields of returned bots.
func TestRefreshAndSummarizeMultipleBotsAvailable(t *testing.T) {
	Convey("with two duts available", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{"dut_1", "dut_2"})

		Convey("refresh without filter refreshes both duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 2)
			So(refreshed.DutIds, ShouldContain, "dut_1")
			So(refreshed.DutIds, ShouldContain, "dut_2")

			Convey("then summarize without filter summarizes both duts", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
				So(err, ShouldBeNil)

				duts := extractSummarizedDutIDs(summarized)
				So(duts, ShouldHaveLength, 2)
				So(duts, ShouldContain, "dut_1")
				So(duts, ShouldContain, "dut_2")
			})
		})

		Convey("refresh with 2 filters matching existing duts refreshes both duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{"dut_1", "dut_2"}),
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 2)
			So(refreshed.DutIds, ShouldContain, "dut_1")
			So(refreshed.DutIds, ShouldContain, "dut_2")

			Convey("then summarize filtering one available dut and one unknown dut refreshes one dut", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1", "dut_non_existent"}),
				})
				So(err, ShouldBeNil)

				duts := extractSummarizedDutIDs(summarized)
				So(duts, ShouldHaveLength, 1)
				So(duts, ShouldContain, "dut_1")
			})
		})
	})
}

// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the fields of returned bots.
func TestRefreshLargeNumberOfBotsAvailable(t *testing.T) {
	Convey("with a large number of duts available", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		// More DUTs to refresh than WorkPool concurrency.
		numDuts := 3 * clients.MaxConcurrentSwarmingCalls
		dutNames := make([]string, 0, numDuts)
		for i := 0; i < numDuts; i++ {
			dutNames = append(dutNames, fmt.Sprintf("dut_%d", i))
		}
		tf.FakeSwarming.setAvailableDutIDs(dutNames)

		Convey("refresh selecting all the DUTs refreshes all duts", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts(dutNames),
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, numDuts)
			for _, d := range dutNames {
				So(refreshed.DutIds, ShouldContain, d)
			}
		})
	})
}

func TestRefreshAndSummarizeBotsDutState(t *testing.T) {
	Convey("with a swarming dut in state needs_reset", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.botInfos = make(map[string]*swarming.SwarmingRpcsBotInfo)
		tf.FakeSwarming.botInfos["bot_dut_1"] = &swarming.SwarmingRpcsBotInfo{
			BotId: "bot_dut_1",
			Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{
					Key:   "dut_id",
					Value: []string{"dut_1"},
				},
				{
					Key:   "dut_state",
					Value: []string{"needs_reset"},
				},
			},
		}

		Convey("refresh with empty filter", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{}),
			})
			So(err, ShouldBeNil)

			Convey("then summarizing without filter summarizes bot with state needs_reset", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)

				bot := summarized.Bots[0]
				So(bot.DutId, ShouldEqual, "dut_1")
				So(bot.DutState, ShouldEqual, fleet.DutState_NeedsReset)
			})
		})
	})
}

func TestRefreshAndSummarizeIdleDuration(t *testing.T) {
	Convey("with a swarming dut with no recent tasks", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})

		Convey("refresh with empty filter", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{}),
			})
			So(err, ShouldBeNil)

			Convey("then summarizing without filter summarizes dut with unknown idle duration", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)

				bot := summarized.Bots[0]
				So(bot.DutId, ShouldEqual, "dut_task_1")
				So(bot.IdleDuration, ShouldBeNil)
			})
		})
	})

	Convey("with a swarming dut with one recent completed task", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})
		tf.FakeSwarming.botTasks["bot_dut_task_1"] = []*swarming.SwarmingRpcsTaskResult{
			{
				State:       "COMPLETED",
				CompletedTs: "2016-01-02T10:04:05.999999999",
			},
		}

		Convey("refresh with empty filter", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{}),
			})
			So(err, ShouldBeNil)

			Convey("then summarizing without filter summarizes dut with sane idle duration", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)

				bot := summarized.Bots[0]
				So(bot.DutId, ShouldEqual, "dut_task_1")
				So(bot.IdleDuration, ShouldNotBeNil)
				So(bot.IdleDuration.Seconds, ShouldBeGreaterThan, 0)
			})
		})
	})

	Convey("with a swarming dut with one running task", t, func() {
		tf, cleanup := newTestFixtureWithFakeSwarming(t)
		defer cleanup()
		tf.FakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})
		tf.FakeSwarming.botTasks["bot_dut_task_1"] = []*swarming.SwarmingRpcsTaskResult{
			{
				State: "RUNNING",
			},
		}

		Convey("refresh with empty filter", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: makeBotSelectorForDuts([]string{}),
			})
			So(err, ShouldBeNil)

			Convey("then summarizing without filter summarizes dut with idle duration zero", func() {
				summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)

				bot := summarized.Bots[0]
				So(bot.DutId, ShouldEqual, "dut_task_1")
				So(bot.IdleDuration, ShouldNotBeNil)
				So(bot.IdleDuration.Seconds, ShouldEqual, 0)
				So(bot.IdleDuration.Nanos, ShouldEqual, 0)
			})
		})
	})
}

func TestRefreshBotsWithDimensions(t *testing.T) {
	Convey("with three swarming duts with various models and pools", t, func() {
		tf, cleanup := newTestFixture(t)
		defer cleanup()

		b1 := readyBotsForDutIDs([]string{"dut_cq_link"})[0]
		setBotDimension(b1, "label-pool", []string{"cq"})
		setBotDimension(b1, "label-model", []string{"link"})
		b2 := readyBotsForDutIDs([]string{"dut_cq_lumpy"})[0]
		setBotDimension(b2, "label-pool", []string{"cq"})
		setBotDimension(b2, "label-model", []string{"lumpy"})
		b3 := readyBotsForDutIDs([]string{"dut_bvt_lumpy"})[0]
		setBotDimension(b3, "label-pool", []string{"bvt"})
		setBotDimension(b3, "label-model", []string{"lumpy"})
		bots := []*swarming.SwarmingRpcsBotInfo{b1, b2, b3}

		tf.MockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		tf.MockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("refresh filtering by pool works", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: []*fleet.BotSelector{
					{Dimensions: &fleet.BotDimensions{Pools: []string{"cq"}}},
				},
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 2)
			So(refreshed.DutIds, ShouldContain, "dut_cq_link")
			So(refreshed.DutIds, ShouldContain, "dut_cq_lumpy")
		})

		Convey("refresh filtering by model works", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: []*fleet.BotSelector{
					{Dimensions: &fleet.BotDimensions{Model: "lumpy"}},
				},
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 2)
			So(refreshed.DutIds, ShouldContain, "dut_cq_lumpy")
			So(refreshed.DutIds, ShouldContain, "dut_bvt_lumpy")
		})

		Convey("refresh filtering by pool and model works", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{
				Selectors: []*fleet.BotSelector{
					{Dimensions: &fleet.BotDimensions{Pools: []string{"cq"}, Model: "lumpy"}},
				},
			})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 1)
			So(refreshed.DutIds, ShouldContain, "dut_cq_lumpy")
		})
	})
}

func TestSummarizeBotsWithDimensions(t *testing.T) {
	Convey("for a bot with non-trivial dimensions", t, func() {
		tf, cleanup := newTestFixture(t)
		defer cleanup()

		bots := readyBotsForDutIDs([]string{"dut_cq_link"})
		b := bots[0]
		setBotDimension(b, "label-pool", []string{"cq", "bvt"})
		setBotDimension(b, "label-model", []string{"link"})

		tf.MockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		tf.MockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("refresh and summarize without filter include non-trivial dimensions", func() {
			refreshed, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 1)
			So(refreshed.DutIds, ShouldContain, "dut_cq_link")

			summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
			So(err, ShouldBeNil)
			So(summarized.Bots, ShouldHaveLength, 1)
			So(summarized.Bots[0].Dimensions, ShouldNotBeNil)
			So(summarized.Bots[0].Dimensions.Pools, ShouldHaveLength, 2)
			So(summarized.Bots[0].Dimensions.Pools, ShouldContain, "cq")
			So(summarized.Bots[0].Dimensions.Pools, ShouldContain, "bvt")
			So(summarized.Bots[0].Dimensions.Model, ShouldEqual, "link")
		})
	})
}

func TestHealthSummary(t *testing.T) {
	Convey("with one bot available in state ready", t, func() {
		tf, cleanup := newTestFixture(t)
		defer cleanup()

		bots := readyBotsForDutIDs([]string{"dut_ready"})
		tf.MockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		tf.MockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("bot summary reports the bot healthy", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
			So(err, ShouldBeNil)
			So(summarized.Bots, ShouldHaveLength, 1)
			So(summarized.Bots[0].Health, ShouldEqual, fleet.Health_Healthy)
		})
	})

	Convey("with one bot available in state repair_failed", t, func() {
		tf, cleanup := newTestFixture(t)
		defer cleanup()

		bots := readyBotsForDutIDs([]string{"dut_repair_failed"})
		b := bots[0]
		setBotDimension(b, "dut_state", []string{"repair_failed"})
		tf.MockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		tf.MockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("bot summary reports the bot unhealthy", func() {
			_, err := tf.Tracker.RefreshBots(tf.C, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			summarized, err := tf.Tracker.SummarizeBots(tf.C, &fleet.SummarizeBotsRequest{})
			So(err, ShouldBeNil)
			So(summarized.Bots, ShouldHaveLength, 1)
			So(summarized.Bots[0].Health, ShouldEqual, fleet.Health_Unhealthy)
		})
	})
}

// extractSummarizedDutIDs extracts the DutIDs of the the summarized bots.
func extractSummarizedDutIDs(resp *fleet.SummarizeBotsResponse) []string {
	var duts []string
	for _, bot := range resp.Bots {
		duts = append(duts, bot.DutId)
	}
	return duts
}
