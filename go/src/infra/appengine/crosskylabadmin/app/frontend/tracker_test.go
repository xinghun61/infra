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
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/clients/mock"
	"infra/appengine/crosskylabadmin/app/config"
)

// TestRefreshAndSummarizeBots tests the RefreshBots-SummarizeBots API.
// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the other fields of returned bots.
func TestRefreshAndSummarizeBots(t *testing.T) {
	Convey("In testing context", t, FailureHalts, func() {
		c := testingContext()
		fakeSwarming := &fakeSwarmingClient{
			pool:    config.Get(c).Swarming.BotPool,
			taskIDs: map[*clients.SwarmingCreateTaskArgs]string{},
		}
		tracker := TrackerServerImpl{
			ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
				return fakeSwarming, nil
			},
		}

		Convey("with no swarming duts available", func() {
			fakeSwarming.setAvailableDutIDs([]string{})

			Convey("refresh without filter", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})

			})

			Convey("refresh with empty filter", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})
			})

			Convey("refresh with non-empty filter", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})

				Convey("then summarize without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})

				Convey("then summarize with empty filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{}),
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})

				Convey("then summarize with non-empty filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})
			})
		})

		Convey("with a single dut available", func() {
			fakeSwarming.setAvailableDutIDs([]string{"dut_1"})

			Convey("refresh filtering to available dut", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				})

				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh avilable dut", func() {
					So(refreshed.DutIds, ShouldHaveLength, 1)
					So(refreshed.DutIds, ShouldContain, "dut_1")
				})
			})

			Convey("refresh filtering to unknown dut", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_2"}),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})
			})

			Convey("refresh without filter", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})

				Convey("should refresh available dut", func() {
					So(refreshed.DutIds, ShouldHaveLength, 1)
					So(refreshed.DutIds, ShouldContain, "dut_1")
				})

				Convey("then summarize without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize available dut", func() {
						duts := extractSummarizedDutIDs(summarized)
						So(duts, ShouldHaveLength, 1)
						So(duts, ShouldContain, "dut_1")
					})
				})

				Convey("then summarize with empty filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: []*fleet.BotSelector{{}},
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})

				Convey("then summarize filtering to available dut", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize available dut", func() {
						duts := extractSummarizedDutIDs(summarized)
						So(duts, ShouldHaveLength, 1)
						So(duts, ShouldContain, "dut_1")
					})
				})

				Convey("then summarize filtering to unknown dut", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{"dut_2"}),
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})
			})
		})
		Convey("with two duts available", func() {
			fakeSwarming.setAvailableDutIDs([]string{"dut_1", "dut_2"})

			Convey("refresh without filter", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})

				Convey("should refresh available duts", func() {
					So(refreshed.DutIds, ShouldHaveLength, 2)
					So(refreshed.DutIds, ShouldContain, "dut_1")
					So(refreshed.DutIds, ShouldContain, "dut_2")
				})

				Convey("then summarize without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize available duts", func() {
						duts := extractSummarizedDutIDs(summarized)
						So(duts, ShouldHaveLength, 2)
						So(duts, ShouldContain, "dut_1")
						So(duts, ShouldContain, "dut_2")
					})
				})
			})

			Convey("refresh with 2 filters matching existing duts", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1", "dut_2"}),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh available duts", func() {
					So(refreshed.DutIds, ShouldHaveLength, 2)
					So(refreshed.DutIds, ShouldContain, "dut_1")
					So(refreshed.DutIds, ShouldContain, "dut_2")
				})

				Convey("then summarize filtering one available dut and one unknown dut", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{"dut_1", "dut_non_existent"}),
					})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize available dut", func() {
						duts := extractSummarizedDutIDs(summarized)
						So(duts, ShouldHaveLength, 1)
						So(duts, ShouldContain, "dut_1")
					})
				})
			})
		})

		// More DUTs to refresh than WorkPool concurrency.
		Convey("with a large number of duts available", func() {
			numDuts := 3 * clients.MaxConcurrentSwarmingCalls
			dutNames := make([]string, 0, numDuts)
			for i := 0; i < numDuts; i++ {
				dutNames = append(dutNames, fmt.Sprintf("dut_%d", i))
			}
			fakeSwarming.setAvailableDutIDs(dutNames)
			Convey("refresh selecting all the DUTs", func() {
				refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts(dutNames),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh available duts", func() {
					So(refreshed.DutIds, ShouldHaveLength, numDuts)
					for _, d := range dutNames {
						So(refreshed.DutIds, ShouldContain, d)
					}
				})
			})
		})
	})
}

func TestRefreshAndSummarizeBotsFields(t *testing.T) {
	Convey("In testing context", t, FailureHalts, func() {
		c := testingContext()
		fakeSwarming := &fakeSwarmingClient{
			pool:    config.Get(c).Swarming.BotPool,
			taskIDs: map[*clients.SwarmingCreateTaskArgs]string{},
		}
		tracker := TrackerServerImpl{
			ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
				return fakeSwarming, nil
			},
		}

		Convey("with a swarming dut in state needs_reset", func() {
			fakeSwarming.botInfos = make(map[string]*swarming.SwarmingRpcsBotInfo)
			fakeSwarming.botInfos["bot_dut_1"] = &swarming.SwarmingRpcsBotInfo{
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
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				Convey("should refresh the dut", func() {
					So(err, ShouldBeNil)
				})
				Convey("then summarizing without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{}),
					})
					Convey("should summarize available dut with the right state", func() {
						So(err, ShouldBeNil)
						So(summarized.Bots, ShouldHaveLength, 1)
						bot := summarized.Bots[0]
						So(bot.DutId, ShouldEqual, "dut_1")
						So(bot.DutState, ShouldEqual, fleet.DutState_NeedsReset)
					})
				})
			})
		})

		Convey("with a swarming dut with no recent tasks", func() {
			fakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})
			Convey("refresh with empty filter", func() {
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				Convey("should refresh the dut", func() {
					So(err, ShouldBeNil)
				})
				Convey("then summarizing without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{}),
					})
					Convey("should summarize available dut with nil IdleDuration", func() {
						So(err, ShouldBeNil)
						So(summarized.Bots, ShouldHaveLength, 1)
						bot := summarized.Bots[0]
						So(bot.DutId, ShouldEqual, "dut_task_1")
						So(bot.IdleDuration, ShouldBeNil)
					})
				})
			})
		})

		Convey("with a swarming dut with one recent completed task", func() {
			fakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})
			fakeSwarming.botTasks["bot_dut_task_1"] = []*swarming.SwarmingRpcsTaskResult{
				{
					State:       "COMPLETED",
					CompletedTs: "2016-01-02T10:04:05.999999999",
				},
			}
			Convey("refresh with empty filter", func() {
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				Convey("should refresh the dut", func() {
					So(err, ShouldBeNil)
				})
				Convey("then summarizing without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{}),
					})
					Convey("should summarize available dut with positive IdleDuration", func() {
						So(err, ShouldBeNil)
						So(summarized.Bots, ShouldHaveLength, 1)
						bot := summarized.Bots[0]
						So(bot.DutId, ShouldEqual, "dut_task_1")
						So(bot.IdleDuration, ShouldNotBeNil)
						So(bot.IdleDuration.Seconds, ShouldBeGreaterThan, 0)
					})
				})
			})
		})

		Convey("with a swarming dut with one running task", func() {
			fakeSwarming.setAvailableDutIDs([]string{"dut_task_1"})
			fakeSwarming.botTasks["bot_dut_task_1"] = []*swarming.SwarmingRpcsTaskResult{
				{
					State: "RUNNING",
				},
			}
			Convey("refresh with empty filter", func() {
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{}),
				})
				Convey("should refresh the dut", func() {
					So(err, ShouldBeNil)
				})
				Convey("then summarizing without filter", func() {
					summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{
						Selectors: makeBotSelectorForDuts([]string{}),
					})
					Convey("should summarize available dut with zero IdleDuration", func() {
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
		})
	})
}

func TestRefreshBotsWithDimensions(t *testing.T) {
	Convey("with three swarming duts with various models and pools", t, func() {
		c := testingContext()
		mc := gomock.NewController(t)
		defer mc.Finish()
		mockSwarming := mock.NewMockSwarmingClient(mc)
		tracker := TrackerServerImpl{
			ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
				return mockSwarming, nil
			},
		}

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

		mockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(c).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		mockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("refresh filtering by pool works", func() {
			refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
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
			refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
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
			refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{
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
		c := testingContext()
		mc := gomock.NewController(t)
		defer mc.Finish()
		mockSwarming := mock.NewMockSwarmingClient(mc)
		tracker := TrackerServerImpl{
			ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
				return mockSwarming, nil
			},
		}

		bots := readyBotsForDutIDs([]string{"dut_cq_link"})
		b := bots[0]
		setBotDimension(b, "label-pool", []string{"cq", "bvt"})
		setBotDimension(b, "label-model", []string{"link"})

		mockSwarming.EXPECT().ListAliveBotsInPool(
			gomock.Any(), gomock.Eq(config.Get(c).Swarming.BotPool), gomock.Any(),
		).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))
		mockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("refresh and summarize without filter include non-trivial dimensions", func() {
			refreshed, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
			So(err, ShouldBeNil)
			So(refreshed.DutIds, ShouldHaveLength, 1)
			So(refreshed.DutIds, ShouldContain, "dut_cq_link")

			summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
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
	Convey("in testing context", t, func() {
		c := testingContext()
		mc := gomock.NewController(t)
		defer mc.Finish()
		mockSwarming := mock.NewMockSwarmingClient(mc)
		tracker := TrackerServerImpl{
			ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
				return mockSwarming, nil
			},
		}
		mockSwarming.EXPECT().ListSortedRecentTasksForBot(
			gomock.Any(), gomock.Any(), gomock.Any(),
		).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{}, nil)

		Convey("with one bot available in state ready", func() {
			bots := readyBotsForDutIDs([]string{"dut_ready"})
			mockSwarming.EXPECT().ListAliveBotsInPool(
				gomock.Any(), gomock.Eq(config.Get(c).Swarming.BotPool), gomock.Any(),
			).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))

			Convey("bot summary reports the bot healthy", func() {
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
				So(err, ShouldBeNil)
				summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)
				So(summarized.Bots[0].Health, ShouldEqual, fleet.Health_Healthy)
			})
		})

		Convey("with one bot available in state repair_failed", func() {
			bots := readyBotsForDutIDs([]string{"dut_repair_failed"})
			b := bots[0]
			setBotDimension(b, "dut_state", []string{"repair_failed"})
			mockSwarming.EXPECT().ListAliveBotsInPool(
				gomock.Any(), gomock.Eq(config.Get(c).Swarming.BotPool), gomock.Any(),
			).AnyTimes().DoAndReturn(fakeListAliveBotsInPool(bots))

			Convey("bot summary reports the bot unhealthy", func() {
				_, err := tracker.RefreshBots(c, &fleet.RefreshBotsRequest{})
				So(err, ShouldBeNil)
				summarized, err := tracker.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
				So(err, ShouldBeNil)
				So(summarized.Bots, ShouldHaveLength, 1)
				So(summarized.Bots[0].Health, ShouldEqual, fleet.Health_Unhealthy)
			})
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
