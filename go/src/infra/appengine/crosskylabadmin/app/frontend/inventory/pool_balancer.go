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

package inventory

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"

	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// poolBalancer encapsulates the pool balancing algorithm.
type poolBalancer struct {
	Target map[string]fleet.Health
	Spare  map[string]fleet.Health

	targetName string
	spareName  string
}

func newPoolBalancer(duts []*inventory.DeviceUnderTest, target, spare string) (*poolBalancer, error) {
	dp, err := mapPoolsToDUTs(duts)
	if err != nil {
		return nil, err
	}

	pb := &poolBalancer{
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

func (pb *poolBalancer) TargetHealthyCount() int {
	return len(getHealthy(pb.Target))
}

func (pb *poolBalancer) SpareHealthyCount() int {
	return len(getHealthy(pb.Spare))
}

// EnsureTargetHealthy balances the pools so that target pool has healthy DUTs.
//
// This function returns the recommended changes and also any failures encountered.
// This function also applies the recommended changes to the poolBalancer state.
func (pb *poolBalancer) EnsureTargetHealthy(maxUnhealthyDUTs int) ([]*fleet.PoolChange, []fleet.EnsurePoolHealthyResponse_Failure) {
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

func resizePool(duts []*inventory.DeviceUnderTest, targetPool string, targetSize int, sparePool string) ([]*fleet.PoolChange, error) {
	errStr := fmt.Sprintf("resizePool %s pool to %d DUTs using %s spare pool", targetPool, targetSize, sparePool)
	dp, err := mapPoolsToDUTs(duts)
	if err != nil {
		return []*fleet.PoolChange{}, errors.Annotate(err, errStr).Err()
	}

	ts := dp[targetPool]
	ss := dp[sparePool]
	switch {
	case len(ts) < targetSize:
		want := targetSize - len(ts)
		if want > len(ss) {
			return []*fleet.PoolChange{}, status.Errorf(codes.ResourceExhausted, "%s: insufficient spares (want %d, have %d)", errStr, want, len(ss))
		}
		return changeDUTPools(ss[:want], sparePool, targetPool), nil
	case len(ts) > targetSize:
		return changeDUTPools(ts[:len(ts)-targetSize], targetPool, sparePool), nil
	default:
		// targetPool is already the right size.
		return []*fleet.PoolChange{}, nil
	}
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
