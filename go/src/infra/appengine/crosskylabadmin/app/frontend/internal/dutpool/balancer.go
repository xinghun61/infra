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
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"
)

// Balancer encapsulates the pool balancing algorithm.
//
// Use EnsureTargetHealthy() to execute the pool balancing algorithm on an
// initialized Balancer.
type Balancer struct {
	Target map[string]fleet.Health
	Spare  map[string]fleet.Health

	targetName string
	spareName  string
}

// NewBalancer returns an initialized Balancer.
func NewBalancer(duts []*inventory.DeviceUnderTest, target, spare string) (*Balancer, error) {
	dp, err := mapPoolsToDUTs(duts)
	if err != nil {
		return nil, err
	}

	pb := &Balancer{
		Target: make(map[string]fleet.Health),
		Spare:  make(map[string]fleet.Health),

		targetName: target,
		spareName:  spare,
	}
	for _, d := range dp[target] {
		pb.Target[d] = fleet.Health_HealthInvalid
	}
	for _, d := range dp[spare] {
		pb.Spare[d] = fleet.Health_HealthInvalid
	}
	return pb, nil
}

// FillInHealth fills in the health info for each DUT.
func (pb *Balancer) FillInHealth(botsHealth map[string]fleet.Health) {
	for d := range pb.Target {
		if val, ok := botsHealth[d]; ok {
			pb.Target[d] = val
		}
	}

	for d := range pb.Spare {
		if val, ok := botsHealth[d]; ok {
			pb.Spare[d] = val
		}
	}
}

// TargetHealthyCount counts the number of healthy DUTs in the target pool.
func (pb *Balancer) TargetHealthyCount() int {
	return len(getHealthy(pb.Target))
}

// SpareHealthyCount counts the number of healthy DUTs in the spare pool.
func (pb *Balancer) SpareHealthyCount() int {
	return len(getHealthy(pb.Spare))
}

// EnsureTargetHealthy balances the pools so that target pool has healthy DUTs.
//
// This function returns the recommended changes and also any failures encountered.
// This function also applies the recommended changes to the Balancer state.
func (pb *Balancer) EnsureTargetHealthy(maxUnhealthyDUTs int) ([]*fleet.PoolChange, []fleet.EnsurePoolHealthyResponse_Failure) {
	need := getUnhealthy(pb.Target)
	if maxUnhealthyDUTs > 0 && len(need) > maxUnhealthyDUTs {
		return []*fleet.PoolChange{}, []fleet.EnsurePoolHealthyResponse_Failure{fleet.EnsurePoolHealthyResponse_TOO_MANY_UNHEALTHY_DUTS}
	}

	have := getHealthy(pb.Spare)

	changes := make([]*fleet.PoolChange, 0, 2*minInt(len(need), len(have)))
	failures := []fleet.EnsurePoolHealthyResponse_Failure{}
	for i, n := range need {
		if i >= len(have) {
			failures = append(failures, fleet.EnsurePoolHealthyResponse_NOT_ENOUGH_HEALTHY_SPARES)
			break
		}
		h := have[i]

		pb.Spare[n] = pb.Target[n]
		delete(pb.Target, n)
		changes = append(changes, &fleet.PoolChange{
			DutId:   n,
			OldPool: pb.targetName,
			NewPool: pb.spareName,
		})

		pb.Target[h] = pb.Spare[h]
		delete(pb.Spare, h)
		changes = append(changes, &fleet.PoolChange{
			DutId:   h,
			OldPool: pb.spareName,
			NewPool: pb.targetName,
		})
	}
	return changes, failures
}

func getUnhealthy(dutHealths map[string]fleet.Health) []string {
	res := make([]string, 0, len(dutHealths))
	for d, h := range dutHealths {
		if h != fleet.Health_Healthy {
			res = append(res, d)
		}
	}
	return res
}

func getHealthy(dutHealths map[string]fleet.Health) []string {
	res := make([]string, 0, len(dutHealths))
	for d, h := range dutHealths {
		if h == fleet.Health_Healthy {
			res = append(res, d)
		}
	}
	return res
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
