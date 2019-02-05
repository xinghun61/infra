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
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

// TestBestPriority tests that BestPriorityFor behaves correctly.
func TestBestPriority(t *testing.T) {
	t.Parallel()
	expects := []Priority{
		FreeBucket,
		1,
	}
	actuals := []Priority{
		BestPriorityFor(balance{0, 0, 0}),
		BestPriorityFor(balance{0, 1, 0}),
	}

	for i, expect := range expects {
		actual := actuals[i]
		if actual != expect {
			t.Errorf("BestPriority = %+v, want %+v", actual, expect)
		}
	}
}

// TestAccountAdvanceWithNoOverflow tests that NextBalance behaves correctly
// when an account is not overflowing its MaxBalance.
func TestAccountAdvanceWithNoOverflow(t *testing.T) {
	t.Parallel()
	expect := balance{0, 2, 4}

	config := &AccountConfig{
		ChargeRate:       []float64{1, 2, 3},
		MaxChargeSeconds: 10,
	}
	before := balance{}
	actual := nextBalance(before, config, 2, []int{1, 1, 1})

	if diff := pretty.Compare(actual, expect); diff != "" {
		t.Errorf("Unexpected diff (-got +want): %s", diff)
	}
}

// TestAccountAdvanceWithOverflow tests that NextBalance behaves correctly
// when an account is overflowing its MaxBalance (in particular, that the
// account balance is capped if it is supposed to be).
func TestAccountAdvanceWithOverflow(t *testing.T) {
	t.Parallel()
	expect := []float64{10, 11, 10}
	// P0 bucket will start below max and reach max.
	// P1 bucket will have started above max already, but have spend that causes
	//    it to be pulled to a lower value still above max.
	// P2 bucket will have started above max, but have spend that causes it to be
	//    pulled below max, and then will recharge to reach max again.
	config := &AccountConfig{
		ChargeRate:       []float64{1, 1, 1},
		MaxChargeSeconds: 10,
	}

	before := balance{9.5, 12, 10.5}
	actual := nextBalance(before, config, 1, []int{0, 1, 1})

	if diff := pretty.Compare(actual, expect); diff != "" {
		t.Errorf("Unexpected diff (-got +want): %s", diff)
	}
}
