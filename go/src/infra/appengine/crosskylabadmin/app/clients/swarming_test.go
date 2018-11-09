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

package clients

import (
	"testing"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

func TestGetStateDimension(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name  string
		input []*swarming.SwarmingRpcsStringListPair
		want  fleet.DutState
	}{
		{"missing key", nil, fleet.DutState_DutStateInvalid},
		{"normal", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready"}},
		}, fleet.DutState_Ready},
		{"multiple values", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready", "repair_failed"}},
		}, fleet.DutState_DutStateInvalid},
		{"multiple pairs", []*swarming.SwarmingRpcsStringListPair{
			{Key: "dut_state", Value: []string{"ready"}},
			{Key: "dut_state", Value: []string{"repair_failed"}},
		}, fleet.DutState_Ready},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			got := GetStateDimension(c.input)
			if got != c.want {
				t.Errorf("getStateDimension(%#v) = %#v; want %#v", c.input, got, c.want)
			}
		})
	}
}
