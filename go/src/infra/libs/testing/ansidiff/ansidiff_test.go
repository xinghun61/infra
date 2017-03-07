// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ansidiff

import (
	"fmt"
	"testing"
)

type T1 struct {
	a, b string
}

func TestDiff(t *testing.T) {
	tests := []struct {
		v1, v2 T1
		want   string
	}{
		{
			T1{"foo", "bar"},
			T1{"bar", "baz"},
			fmt.Sprintf("{a:%v%v b:ba%v%v}",
				red("foo"), green("bar"),
				red("r"), green("z")),
		},
	}

	for _, test := range tests {
		got := Diff(test.v1, test.v2)
		if got != test.want {
			t.Errorf("Got %v, want %v", got, test.want)
		}
	}

}
