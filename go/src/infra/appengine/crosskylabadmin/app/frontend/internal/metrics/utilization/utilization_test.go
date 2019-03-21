// Copyright 2019 The LUCI Authors.
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

package utilization

import (
	"context"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/tsmon"
)

func TestReportMetrics(t *testing.T) {
	Convey("with fake tsmon context", t, func() {
		ctx := context.Background()
		ctx, _ = tsmon.WithDummyInMemory(ctx)

		Convey("ReportMetric for single bot should report 0 for unknown statuses", func() {
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{
				{State: "", Dimensions: []*swarming.SwarmingRpcsStringListPair{}},
			})
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "[None]", false), ShouldEqual, 1)

			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "Repairing", false), ShouldEqual, 0)
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "Running", false), ShouldEqual, 0)
		})

		Convey("ReportMetric for multiple bots with same fields should count up", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Ready", false), ShouldEqual, 3)
		})

		Convey("ReportMetric with managed pool should report pool correctly", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"DUT_POOL_CQ"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "managed:DUT_POOL_CQ", "Ready", false), ShouldEqual, 1)
			So(dutmonMetric.Get(ctx, "reef", "electro", "DUT_POOL_CQ", "Ready", false), ShouldEqual, 0)
		})
	})
}
