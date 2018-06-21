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

package app

import (
	"fmt"
	"testing"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"golang.org/x/net/context"

	"infra/appengine/crosskylabadmin/api/fleet/v1"

	. "github.com/smartystreets/goconvey/convey"
)

// TestRefreshAndSummarizeBots tests the RefreshBots-SummarizeBots API.
// This function only validates the DutID field, to ensure that the correct bots are updated/summarized.
// Other tests should verify the other fields of returned bots.
func TestRefreshAndSummarizeBots(t *testing.T) {
	t.Parallel()

	Convey("In testing context", t, FailureHalts, func() {
		c := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
		datastore.GetTestable(c).Consistent(true)
		fsc := fakeSwarmingClient{
			t:    t,
			pool: swarmingBotPool,
		}
		server := trackerServerImpl{
			swarmingClientHook: func(context.Context, string) (SwarmingClient, error) {
				return &fsc, nil
			},
		}

		Convey("with no swarming duts available", func() {
			setAvailableDutIDs(&fsc, []string{})

			Convey("refresh without filter", func() {
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})

			})

			Convey("refresh with empty filter", func() {
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
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
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
					Selectors: makeBotSelectorForDuts([]string{"dut_1"}),
				})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})
				Convey("should refresh nothing", func() {
					So(refreshed.DutIds, ShouldBeEmpty)
				})

				Convey("then summarize without filter", func() {
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
					Convey("should succeed", func() {
						So(err, ShouldBeNil)
					})
					Convey("should summarize nothing", func() {
						So(summarized.Bots, ShouldBeEmpty)
					})
				})

				Convey("then summarize with empty filter", func() {
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
			setAvailableDutIDs(&fsc, []string{"dut_1"})

			Convey("refresh filtering to available dut", func() {
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
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
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
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
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})

				Convey("should refresh available dut", func() {
					So(refreshed.DutIds, ShouldHaveLength, 1)
					So(refreshed.DutIds, ShouldContain, "dut_1")
				})

				Convey("then summarize without filter", func() {
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
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
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
			setAvailableDutIDs(&fsc, []string{"dut_1", "dut_2"})

			Convey("refresh without filter", func() {
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{})
				Convey("should succeed", func() {
					So(err, ShouldBeNil)
				})

				Convey("should refresh available duts", func() {
					So(refreshed.DutIds, ShouldHaveLength, 2)
					So(refreshed.DutIds, ShouldContain, "dut_1")
					So(refreshed.DutIds, ShouldContain, "dut_2")
				})

				Convey("then summarize without filter", func() {
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{})
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
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
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
					summarized, err := server.SummarizeBots(c, &fleet.SummarizeBotsRequest{
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
			numDuts := 3 * maxConcurrentSwarmingCalls
			dutNames := make([]string, 0, numDuts)
			for i := 0; i < numDuts; i++ {
				dutNames = append(dutNames, fmt.Sprintf("dut_%d", i))
			}
			setAvailableDutIDs(&fsc, dutNames)
			Convey("refresh selecting all the DUTs", func() {
				refreshed, err := server.RefreshBots(c, &fleet.RefreshBotsRequest{
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

// fakeSwarmingClient implements SwarmingClient.
type fakeSwarmingClient struct {
	t *testing.T

	// pool is the single common pool that all bots belong to.
	pool string

	// botInfo maps the dut_id for a bot to its swarming.SwarmingRpcsBotInfo
	botInfos map[string]*swarming.SwarmingRpcsBotInfo
}

// ListAliveBotsInPool is a fake implementation of SwarmingClient.ListAliveBotsInPool.
// This function is intentionally simple. It only supports filtering by dut_id dimension.
func (fsc *fakeSwarmingClient) ListAliveBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	resp := []*swarming.SwarmingRpcsBotInfo{}
	if pool != fsc.pool {
		return resp, nil
	}
	switch len(dims) {
	case 0:
		for _, bi := range fsc.botInfos {
			resp = append(resp, bi)
		}
	case 1:
		k := dims.Get("dut_id")
		if k == "" {
			fsc.t.Fatalf("got dims %s, want a single key: dut_id", dims)
		}
		bi, ok := fsc.botInfos[k]
		if ok {
			resp = append(resp, bi)
		}
	}
	return resp, nil
}

func setAvailableDutIDs(sc *fakeSwarmingClient, duts []string) {
	sc.botInfos = make(map[string]*swarming.SwarmingRpcsBotInfo)
	for _, d := range duts {
		sc.botInfos[d] = &swarming.SwarmingRpcsBotInfo{
			BotId: fmt.Sprintf("bot_%s", d),
			Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{
					Key:   "dut_id",
					Value: []string{d},
				},
			},
		}
	}
}

// makeBotSelector returns a fleet.BotSelector selecting each of the duts
// recognized by the given Dut IDs.
func makeBotSelectorForDuts(duts []string) []*fleet.BotSelector {
	var bs []*fleet.BotSelector
	for _, d := range duts {
		bs = append(bs, &fleet.BotSelector{DutId: d})
	}
	return bs
}

// extractSummarizedDutIDs extracts the DutIDs of the the summarized bots.
func extractSummarizedDutIDs(resp *fleet.SummarizeBotsResponse) []string {
	var duts []string
	for _, bot := range resp.Bots {
		duts = append(duts, bot.DutId)
	}
	return duts
}
