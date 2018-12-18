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
const NumPriorities = 3

// IntVector is the integer equivalent of Vector, to store things
// like per-bucket counts. It doesn't have an underlying Proto, because it
// is only used internally within qslib, never persisted.
//
// TODO(akeshet): Consider renaming this to something that makes it more obvious
// what it is.
type IntVector [NumPriorities]int

// TODO(akeshet): Go through the scheduler code and turn most instance of []float64{}
// into type balance.
// TODO(akeshet): Rename this to an exported field.
type balance [NumPriorities]float64

// Copy returns a copy of the given vector.
// TODO(akeshet): Delete this method, or turn it into a pointer method.
func (a balance) Copy() balance {
	b := balance{}
	copy(b[:], a[:])
	return b
}

// Less determines whether Vector a is less than b, based on
// priority ordered comparison
func (a balance) Less(b balance) bool {
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

// TODO(akeshet): Rename Plus->Add, Minus->Sub, for better consistenct with go libraries.

// Plus returns the sum of two vectors.
func (a balance) Plus(b balance) balance {
	bb := balance{}
	copy(bb[:], a[:])
	for i, v := range b {
		bb[i] += v
	}
	return bb
}

// Minus returns the difference of two vectors.
func (a balance) Minus(b balance) balance {
	bb := balance{}
	copy(bb[:], a[:])
	for i, v := range b {
		bb[i] -= v
	}
	return bb
}

// Equal returns true if two given vectors are equal.
func (a balance) Equal(b balance) bool {
	for i, vA := range a {
		if vA != b[i] {
			return false
		}
	}
	return true
}
