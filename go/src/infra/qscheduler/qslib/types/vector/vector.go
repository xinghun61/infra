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
Package vector implements a protobuf-backed Vector of a compile-time known
length, used to store quota account values, as part of the quota scheduler
algorithm.
*/
package vector

import (
	"fmt"
)

// NumPriorities is the number of distinct priority buckets. For performance
// and code complexity reasons, this is a compile-time constant.
const NumPriorities = 3

// IntVector is the integer equivalent of Vector, to store things
// like per-bucket counts. It doesn't have an underlying Proto, because it
// is only used internally within qslib, never persisted.
type IntVector [NumPriorities]int

// New creates an new 0-initialized Vector with the correct
// underlying slice size.
//
// If len(v) < NumPriorities, then the remaining components of the vector
// will be 0.
//
// If len(b) > NumPriorities, then elements beyond NumPriorities will be
// ignored.
func New(v ...float64) *Vector {
	s := make([]float64, NumPriorities)
	copy(s, v)
	return &Vector{Values: s}
}

// At is a convenience method to return a Vector's component at a given
// priority, without the caller needing to worry about bounds checks.
func (a Vector) At(priority int32) float64 {
	assertLen(&a)
	return a.Values[priority]
}

// assertLen panic()s if v's underlying slice is the incorrect length.
func assertLen(v *Vector) {
	if len(v.Values) != NumPriorities {
		panic(fmt.Sprintf("Vector %#v had length %d instead of %d.",
			v, len(v.Values), NumPriorities))
	}
}

// Less determines whether Vector a is less than b, based on
// priority ordered comparison
func (a Vector) Less(b Vector) bool {
	assertLen(&a)
	assertLen(&b)
	for i, valA := range a.Values {
		valB := b.Values[i]
		if valA < valB {
			return true
		}
		if valB < valA {
			return false
		}
	}
	return false
}

// Plus returns the sum of two vectors.
func (a Vector) Plus(b Vector) Vector {
	// Why a copy a and then add b, instead of a single loop? This works
	// even if len(a.Values) or len(b.Values) < NumPriorities.
	ans := New(a.Values...)
	for i, v := range b.Values {
		ans.Values[i] += v
	}
	return *ans
}

// Minus returns the difference of two vectors.
func (a Vector) Minus(b Vector) Vector {
	ans := New(a.Values...)
	for i, v := range b.Values {
		ans.Values[i] -= v
	}
	return *ans
}

// Equal returns true if two given vectors are equal.
func (a Vector) Equal(b Vector) bool {
	assertLen(&a)
	assertLen(&b)
	for i, vA := range a.Values {
		if vA != b.Values[i] {
			return false
		}
	}
	return true
}
