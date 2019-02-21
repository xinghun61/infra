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

// NumPriorities is the number of distinct priority buckets. For performance
// and code complexity reasons, this is a compile-time constant.
const NumPriorities = 5

// Balance is a vector that represents a cost or account balance.
type Balance [NumPriorities]float32

// Less determines whether Vector a is less than b, based on
// priority ordered comparison
func (a Balance) Less(b Balance) bool {
	for i, valA := range a {
		valB := b[i]
		if valA < valB {
			return true
		}
		if valB < valA {
			return false
		}
	}
	return false
}

// Add returns the sum of two vectors, as a new vector.
func (a Balance) Add(b *Balance) Balance {
	for i, v := range b {
		a[i] += v
	}
	return a
}

// Sub returns the difference of two vectors, as a new vector.
func (a Balance) Sub(b *Balance) Balance {
	for i, v := range b {
		a[i] -= v
	}
	return a
}
