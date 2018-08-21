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

/*
Package account implements a quota account, as part of the quota scheduler
algorithm.
*/
package account

import "infra/qscheduler/qslib/types/vector"

const (
	// FreeBucket is the free priority bucket, where jobs may run even if they have
	// no quota account or have an empty quota account.
	FreeBucket int32 = vector.NumPriorities

	// PromoteThreshold is the account balance at which the scheduler will consider
	// promoting jobs.
	PromoteThreshold = 5.0

	// DemoteThreshold is the account balance at which the scheduler will consider
	// demoting jobs.
	DemoteThreshold = -5.0
)

// BestPriorityFor determines the highest available priority for a quota
// account, given its balance.
//
// If the account is out of quota, or if the supplied balance is a nil
// pointer, then this returns FreeBucket.
func BestPriorityFor(balance *vector.Vector) int32 {
	if balance == nil {
		return FreeBucket
	}
	for priority, value := range balance.Values {
		if value > 0 {
			return int32(priority)
		}
	}
	return FreeBucket
}

// NextBalance calculates and returns the new balance of a quota account.
//
// The new balance calculation is based on the account's recharge rate,
// maximum balance, and the number of currently running jobs per priority
// bucket for that account.
func NextBalance(balance *vector.Vector, c *Config, elapsedSecs float64, runningJobs *vector.IntVector) *vector.Vector {
	v := vector.New()
	for priority := int32(0); priority < vector.NumPriorities; priority++ {
		val := balance.At(priority)
		val -= elapsedSecs * float64(runningJobs[priority])
		maxBalance := c.ChargeRate.At(priority) * c.MaxChargeSeconds
		// Check for value overflow prior to recharging or capping, because
		// if the account value is already above cap we want to leave it there.
		// It likley got over cap due to preemption reimbursement.
		if val < maxBalance {
			val += elapsedSecs * c.ChargeRate.At(priority)
			if val > maxBalance {
				val = maxBalance
			}
		}
		v.Values[priority] = val
	}

	return v
}

// NewConfig creates a new Config instance with initialized member Vectors.
func NewConfig() *Config {
	return &Config{ChargeRate: vector.New()}
}
