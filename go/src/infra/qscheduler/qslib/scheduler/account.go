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

package scheduler

const (
	// FreeBucket is the free priority bucket, where jobs may run even if they have
	// no quota account or have an empty quota account.
	FreeBucket Priority = NumPriorities

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
func BestPriorityFor(b balance) Priority {
	for priority, value := range b {
		if value > 0 {
			return Priority(priority)
		}
	}
	return FreeBucket
}

// nextBalance calculates and returns the new balance of a quota account.
//
// The new balance calculation is based on the account's recharge rate,
// maximum balance, and the number of currently running jobs per priority
// bucket for that account.
func nextBalance(before balance, c *AccountConfig, elapsedSecs float64, runningJobs []int) balance {
	b := balance{}
	for priority := 0; priority < NumPriorities; priority++ {
		val := before[priority]
		val -= elapsedSecs * float64(runningJobs[priority])
		var chargeRate float64
		if len(c.ChargeRate) > priority {
			chargeRate = c.ChargeRate[priority]
		}
		maxBalance := chargeRate * c.MaxChargeSeconds
		// Check for value overflow prior to recharging or capping, because
		// if the account value is already above cap we want to leave it there.
		// It likley got over cap due to preemption reimbursement.
		if val < maxBalance {
			val += elapsedSecs * c.ChargeRate[priority]
			if val > maxBalance {
				val = maxBalance
			}
		}
		b[priority] = val
	}

	return b
}

// TODO(akeshet): Consider removing the NewConfig helper, as it is not really
// doing any non-trivial initialization, and using inline literals is more go-ish.
// On the other hand, it does make tests and example code more compact and
// readable.

// NewAccountConfig creates a new Config instance.
func NewAccountConfig(fanout int, chargeSeconds float64, chargeRate []float64) *AccountConfig {
	return &AccountConfig{
		ChargeRate:       chargeRate,
		MaxChargeSeconds: chargeSeconds,
		MaxFanout:        int32(fanout),
	}
}
