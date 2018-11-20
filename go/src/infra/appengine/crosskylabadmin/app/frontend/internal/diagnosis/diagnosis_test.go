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

package diagnosis

import (
	"testing"

	"github.com/kylelemons/godebug/pretty"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

func TestStateAnnotator(t *testing.T) {
	t.Parallel()
	var got []stateAnnot
	a := stateAnnotator{prev: fleet.DutState_Ready}
	got = append(got, a.annotate(resultWithState("repair_failed")))
	got = append(got, a.annotate(resultWithState("needs_repair")))
	got = append(got, a.annotate(resultWithState("needs_reset")))
	got = append(got, a.annotate(resultWithState("ready")))
	want := []stateAnnot{
		{before: fleet.DutState_RepairFailed, after: fleet.DutState_Ready},
		{before: fleet.DutState_NeedsRepair, after: fleet.DutState_RepairFailed},
		{before: fleet.DutState_NeedsReset, after: fleet.DutState_NeedsRepair},
		{before: fleet.DutState_Ready, after: fleet.DutState_NeedsReset},
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("annotations differ -want +got, %s", diff)
	}
}

func resultWithState(s string) *swarming.SwarmingRpcsTaskResult {
	return &swarming.SwarmingRpcsTaskResult{
		BotDimensions: []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{s}},
		},
	}
}
