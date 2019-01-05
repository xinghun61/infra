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

package dutpool

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"
)

func mapPoolsToDUTs(duts []*inventory.DeviceUnderTest) (map[string][]string, error) {
	dp := make(map[string][]string)
	for _, d := range duts {
		for _, ep := range d.GetCommon().GetLabels().GetCriticalPools() {
			p := ep.String()
			id := d.GetCommon().GetId()
			if id == "" {
				return dp, fmt.Errorf("inventory contains DUT without ID (hostname: %s)", d.GetCommon().GetHostname())
			}
			_, ok := dp[p]
			if !ok {
				dp[p] = []string{}
			}
			dp[p] = append(dp[p], id)
		}
	}
	return dp, nil
}

func changeDUTPools(duts []string, oldPool, newPool string) []*fleet.PoolChange {
	cs := make([]*fleet.PoolChange, 0, len(duts))
	for _, d := range duts {
		cs = append(cs, &fleet.PoolChange{
			DutId:   d,
			OldPool: oldPool,
			NewPool: newPool,
		})
	}
	return cs
}
