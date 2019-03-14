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

// Package utilization provides functions to report DUT utilization metrics.
package utilization

import (
	"context"

	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var dutmonMetric = metric.NewInt(
	"chromeos/skylab/dut_mon/dut_count",
	"The number of DUTs in a given bucket and status",
	nil,
	field.String("board"),
	field.String("model"),
	field.String("pool"),
	field.String("status"),
	field.Bool("is_locked"),
)

// ReportMetrics reports DUT utilization metrics akin to dutmon in Autotest
//
// The reported fields closely match those reported by dutmon, but the metrics
// path is different.
func ReportMetrics(ctx context.Context, bis []*swarming.SwarmingRpcsBotInfo) {
	c := make(counter)
	for _, bi := range bis {
		b := getBucketForBotInfo(bi)
		s := getStatusForBotInfo(bi)
		c.Increment(b, s)
	}
	c.Report(ctx)
}

// bucket contains static DUT dimensions.
//
// These dimensions do not change often. If all DUTs with a given set of
// dimensions are removed, the related metric is not automatically reset. The
// metric will get reset eventually.
type bucket struct {
	board string
	model string
	pool  string
}

// status is a dynamic DUT dimension.
//
// This dimension changes often. If no DUTs have a particular status value,
// the corresponding metric is immediately reset.
type status string

// List of valid statuses from
// https://chromium.googlesource.com/chromiumos/third_party/autotest/+/e75ac7a5609a1e7463fd7dba9b1890bb0fc94944/client/common_lib/host_states.py#13
var allStatuses = []status{"[Multiple]", "[None]", "Cleaning", "Ready", "RepairFailed", "Repairing", "Resetting", "Running", "Verifying"}

// counter collects number of DUTs per bucket and status.
type counter map[bucket]map[status]int

func (c counter) Increment(b bucket, s status) {
	sc := c[b]
	if sc == nil {
		sc = make(map[status]int)
		c[b] = sc
	}
	sc[s]++
}

func (c counter) Report(ctx context.Context) {
	for b, counts := range c {
		for _, s := range allStatuses {
			// TODO(crbug/929872) Report locked status once DUT leasing is
			// implemented in Skylab.
			dutmonMetric.Set(ctx, int64(counts[s]), b.board, b.model, b.pool, string(s), false)
		}
	}
}

func getBucketForBotInfo(bi *swarming.SwarmingRpcsBotInfo) bucket {
	b := bucket{
		board: "[None]",
		model: "[None]",
		pool:  "[None]",
	}
	for _, d := range bi.Dimensions {
		switch d.Key {
		case "label-board":
			b.board = summarizeValues(d.Value)
		case "label-model":
			b.model = summarizeValues(d.Value)
		case "label-pool":
			b.pool = summarizeValues(d.Value)
		default:
			// Ignore other dimensions.
		}
	}
	return b
}

func getStatusForBotInfo(bi *swarming.SwarmingRpcsBotInfo) status {
	// dutState values are defined at
	// https://chromium.googlesource.com/infra/infra/+/e70c5ed1f9dddec833fad7e87567c0ded19fd565/go/src/infra/cmd/skylab_swarming_worker/internal/botinfo/botinfo.go#32
	dutState := ""
	for _, d := range bi.Dimensions {
		switch d.Key {
		case "dut_state":
			dutState = summarizeValues(d.Value)
			break
		default:
			// Ignore other dimensions.
		}
	}

	// Order matters: a bot may be dead and still have a task associated with it.
	if !isBotHealthy(bi) {
		return "[None]"
	}
	botBusy := bi.TaskId != ""

	switch dutState {
	case "ready":
		if botBusy {
			return "Running"
		}
		return "Ready"

	case "running":
		return "Running"
	case "needs_cleanup":
		// We count time spent waiting for a cleanup task to be assigned as time
		// spent Cleaning.
		return "Cleaning"
	case "needs_reset":
		// We count time spent waiting for a reset task to be assigned as time
		// spent Resetting.
		return "Resetting"
	case "needs_repair":
		// We count time spent waiting for a repair task to be assigned as time
		// spent Repairing.
		return "Repairing"
	case "needs_verify":
		// We count time spent waiting for a verify task to be assigned as time
		// spent Verifying.
		return "Verifying"

	case "repair_failed":
		if botBusy {
			// TODO(pprabhu) Repeated attempts to repair a RepairFailed DUT are
			// better counted towards RepairFailed.
			return "Repairing"
		}
		return "RepairFailed"

	default:
		return "[None]"
	}
}

func isBotHealthy(bi *swarming.SwarmingRpcsBotInfo) bool {
	return !(bi.Deleted || bi.IsDead || bi.Quarantined)
}

func summarizeValues(vs []string) string {
	switch len(vs) {
	case 0:
		return "[None]"
	case 1:
		return vs[0]
	default:
		return "[Multiple]"
	}
}
