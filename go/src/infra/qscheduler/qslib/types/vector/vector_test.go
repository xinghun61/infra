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

package vector

import (
	"testing"
)

func TestVectorCompare(t *testing.T) {
	t.Parallel()

	a := *New(1, 0, 0)
	b := *New(1, 0, 1)
	c := *New(0, 1, 1)
	d := *New(1, 0, 0)
	cases := []struct {
		A      Vector
		B      Vector
		Expect bool
	}{
		{a, a, false},
		{b, a, false},
		{a, b, true},
		{c, a, true},
		{d, a, false},
	}
	for _, c := range cases {
		actual := c.A.Less(c.B)
		if actual != c.Expect {
			t.Errorf("%+v < %+v = %+v, want %+v",
				c.A, c.B, actual, c.Expect)
		}
	}
}

func TestEqual(t *testing.T) {
	t.Parallel()

	cases := []struct {
		A      Vector
		B      Vector
		Expect bool
	}{
		{*New(1), *New(1, 0), true},
		{*New(1), *New(1, 1), false},
		{*New(1), *New(0, 1), false},
		{*New(1), *New(1), true},
		{*New(), *New(), true},
	}
	for _, c := range cases {
		actual := c.A.Equal(c.B)
		if actual != c.Expect {
			t.Errorf("%+v == %+v = %+v, want %+v",
				c.A, c.B, actual, c.Expect)
		}
	}
}

func TestArithmetic(t *testing.T) {
	cases := []struct {
		A           Vector
		B           Vector
		ExpectPlus  Vector
		ExpectMinus Vector
	}{
		{*New(), *New(), *New(), *New()},
		{*New(1), *New(1), *New(2), *New()},
		{*New(1, 2, 3), *New(4, 5, 6), *New(5, 7, 9), *New(-3, -3, -3)},
	}
	for _, c := range cases {
		actualPlus := c.A.Plus(c.B)
		actualMinus := c.A.Minus(c.B)
		if !actualPlus.Equal(c.ExpectPlus) {
			t.Errorf("%v + %v = %v, want %v", c.A, c.B, actualPlus, c.ExpectPlus)
		}
		if !actualMinus.Equal(c.ExpectMinus) {
			t.Errorf("%v - %v = %v, want %v", c.A, c.B, actualMinus, c.ExpectMinus)
		}
	}
}
