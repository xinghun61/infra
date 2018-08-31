// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import "testing"

func TestAdminTaskType_String(t *testing.T) {
	t.Parallel()
	cases := []struct {
		v    AdminTaskType
		want string
	}{
		{Verify, "Verify"},
		{AdminTaskType(99), "AdminTaskType(99)"},
	}
	for _, c := range cases {
		got := c.v.String()
		if got != c.want {
			t.Errorf("String(%#v) = %#v; want %#v", c.v, got, c.want)
		}
	}
}
