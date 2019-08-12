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

package scheduler

import (
	"math"
)

type accountConfigGetter interface {
	getAccountConfig(AccountID) (config *AccountConfig, ok bool)
}

// acGetter is a Config wrapper that implements accountConfigGetter
type acGetter struct {
	*Config
}

func (g acGetter) getAccountConfig(aid AccountID) (config *AccountConfig, ok bool) {
	config, ok = g.AccountConfigs[aid]
	return config, ok
}

// fanoutCounter keeps track of the number of remaining paid jobs allowed
// per fanout group.
type fanoutCounter struct {
	jobsUntilThrottled map[fanoutGroup]int
	configGetter       accountConfigGetter
}

// netFanoutCounter initializes a fanoutCounter
func newFanoutCounter(config *Config) *fanoutCounter {
	return &fanoutCounter{
		jobsUntilThrottled: make(map[fanoutGroup]int),
		configGetter:       acGetter{config},
	}
}

// count counts 1 running job against the given request's fanout group.
func (f *fanoutCounter) count(r *TaskRequest) {
	group := r.fanoutGroup()
	f.jobsUntilThrottled[group] = f.getRemaining(r) - 1
}

// getRemaining gets the remaining paid jobs allowed for the given request's
// fanout group.
func (f *fanoutCounter) getRemaining(r *TaskRequest) int {
	group := r.fanoutGroup()
	if remaining, ok := f.jobsUntilThrottled[group]; ok {
		return remaining
	}

	// Initialize count for this group.
	remaining := 0
	if aConfig, ok := f.configGetter.getAccountConfig(r.AccountID); ok {
		switch aConfig.MaxFanout {
		case 0:
			remaining = math.MaxInt32
		default:
			remaining = int(aConfig.MaxFanout)
		}
	}
	f.jobsUntilThrottled[group] = remaining
	return remaining
}
