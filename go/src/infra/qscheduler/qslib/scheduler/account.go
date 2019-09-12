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

import (
	"infra/qscheduler/qslib/protos"
)

const (
	// FreeBucket is the free priority bucket, where jobs may run even if they have
	// no quota account or have an empty quota account.
	FreeBucket Priority = NumPriorities

	// TODO(akeshet): Make the following thresholds configurable.

	// PromoteThreshold is the account balance at which the scheduler will consider
	// promoting jobs.
	PromoteThreshold = 600.0

	// DemoteThreshold is the account balance at which the scheduler will consider
	// demoting jobs.
	DemoteThreshold = -600.0
)

// AccountConfig represents a single account's config. It is the native struct
// version of the AccountConfig proto.
type AccountConfig struct {
	// ChargeRate is the rates (per second) at which per-priority accounts grow.
	//
	// Conceptually this is the time-averaged number of workers that this account
	// may use, at each priority level.
	ChargeRate Balance
	// MaxChargeSeconds is the maximum amount of time over which this account can
	// accumulate quota before hitting its cap.
	//
	// Conceptually this sets the time window over which the time averaged
	// utilization by this account is measured. Very bursty clients will need to
	// use a wider window, whereas very consistent clients will use a narrow one.
	MaxChargeSeconds float32
	// MaxFanout is the maximum number of concurrent paid jobs for a single
	// provisionable label that this account will pay for (0 = no limit).
	//
	// Additional jobs beyond this may run if there is idle capacity, but they
	// will run in the FreeBucket priority level (except if DisableFreeTasks
	// is true, in which case they will not run).
	MaxFanout int32
	// If DisableFreeTasks is true, then jobs for this account will not start
	// running if they would be run at FreeBucket priority.
	DisableFreeTasks bool
}

// BestPriorityFor determines the highest available priority for a quota
// account, given its balance.
//
// If the account is out of quota, or if the supplied balance is a nil
// pointer, then this returns FreeBucket.
func BestPriorityFor(b Balance) Priority {
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
func nextBalance(balance Balance, c *AccountConfig, elapsedSecs float32, runningJobs []int) Balance {
	var runningJobsArray [NumPriorities]int
	copy(runningJobsArray[:], runningJobs)
	for priority := 0; priority < NumPriorities; priority++ {
		val := balance[priority]
		val -= elapsedSecs * float32(runningJobsArray[priority])
		chargeRate := c.ChargeRate[priority]

		maxBalance := chargeRate * c.MaxChargeSeconds
		// Check for value overflow prior to recharging or capping, because
		// if the account value is already above cap we want to leave it there.
		// It likley got over cap due to preemption reimbursement.
		if val < maxBalance {
			val += elapsedSecs * chargeRate
			if val > maxBalance {
				val = maxBalance
			}
		}
		balance[priority] = val
	}

	return balance
}

// NewAccountConfig creates a new Config instance.
func NewAccountConfig(fanout int, chargeSeconds float32, chargeRate []float32, disableFreeTasks bool) *AccountConfig {
	b := Balance{}
	copy(b[:], chargeRate)
	return &AccountConfig{
		ChargeRate:       b,
		MaxChargeSeconds: chargeSeconds,
		MaxFanout:        int32(fanout),
		DisableFreeTasks: disableFreeTasks,
	}
}

// NewAccountConfigFromProto creates a new Config instance.
func NewAccountConfigFromProto(c *protos.AccountConfig) *AccountConfig {
	return NewAccountConfig(
		int(c.MaxFanout),
		c.MaxChargeSeconds,
		c.ChargeRate,
		c.DisableFreeTasks,
	)
}
