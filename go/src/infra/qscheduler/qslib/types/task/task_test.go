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

package task

import "testing"

func TestLabelSetEquals(t *testing.T) {
	cases := []struct {
		a      LabelSet
		b      LabelSet
		expect bool
	}{
		{[]string{"label1"}, []string{"label1"}, true},
		{[]string{"label1"}, []string{"label2"}, false},
		{[]string{}, []string{}, true},
		{[]string{}, []string{"label1"}, false},
		{[]string{"label1", "label2"}, []string{"label2", "label1"}, true},
		{[]string{"label1", "label2"}, []string{"label1"}, false},
		{[]string{"label1", "label2"}, []string{"label1", "label3"}, false},
	}
	for _, test := range cases {
		actual := test.a.Equal(test.b)
		if actual != test.expect {
			t.Errorf("Equal(%v, %v) = %v, want %v", test.a, test.b, actual, test.expect)
		}
	}
}
