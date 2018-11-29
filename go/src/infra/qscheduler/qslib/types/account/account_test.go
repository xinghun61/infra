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

package account

import (
	"testing"

	"infra/qscheduler/qslib/types/vector"
)

// TestBestPriority tests that BestPriorityFor behaves correctly.
func TestBestPriority(t *testing.T) {
	t.Parallel()
	expects := []int32{
		FreeBucket,
		1,
		FreeBucket,
	}
	actuals := []int32{
		BestPriorityFor(vector.New()),
		BestPriorityFor(vector.New(0, 1, 0)),
		BestPriorityFor(nil),
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
	expect := *vector.New(0, 2, 4)

	config := &Config{
		ChargeRate:       vector.New(1, 2, 3),
		MaxChargeSeconds: 10,
	}
	before := vector.New()
	actual := NextBalance(before, config, 2, &vector.IntVector{1, 1, 1})

	if !actual.Equal(expect) {
		t.Errorf("Balance = %+v, want %+v", actual, expect)
	}
}

// TestAccountAdvanceWithOverflow tests that NextBalance behaves correctly
// when an account is overflowing its MaxBalance (in particular, that the
// account balance is capped if it is supposed to be).
func TestAccountAdvanceWithOverflow(t *testing.T) {
	t.Parallel()
	expect := vector.New(10, 11, 10)
	// P0 bucket will start below max and reach max.
	// P1 bucket will have started above max already, but have spend that causes
	//    it to be pulled to a lower value still above max.
	// P2 bucket will have started above max, but have spend that causes it to be
	//    pulled below max, and then will recharge to reach max again.
	config := &Config{
		ChargeRate:       vector.New(1, 1, 1),
		MaxChargeSeconds: 10,
	}

	before := vector.New(9.5, 12, 10.5)
	actual := NextBalance(before, config, 1, &vector.IntVector{0, 1, 1})

	if !actual.Equal(*expect) {
		t.Errorf("Balance = %+v, want %+v", actual, expect)
	}
}

// TestVectorCompare tests that vector Less method behaves correctly.
func TestVectorCompare(t *testing.T) {
	t.Parallel()

	a := *vector.New(1, 0, 0)
	b := *vector.New(1, 0, 1)
	c := *vector.New(0, 1, 1)
	d := *vector.New(1, 0, 0)

	type tuple struct {
		A      vector.Vector
		B      vector.Vector
		Expect bool
	}
	expects := []tuple{
		{a, a, false},
		{b, a, false},
		{a, b, true},
		{c, a, true},
		{d, a, false},
	}
	for _, expect := range expects {
		if expect.A.Less(expect.B) != expect.Expect {
			t.Fail()
		}
	}
}
