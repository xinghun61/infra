// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import "testing"

func TestGetDutNameFromDimensions(t *testing.T) {
	t.Parallel()
	cases := []struct {
		dimensions string
		hostname   string
	}{
		{
			"{\"label-power\": [\"battery\"], \"environment\": [\"ENVIRONMENT_PROD\"], \"dut_name\": [\"abcd\"]}",
			"abcd",
		},
	}

	for _, c := range cases {
		h, e := getDutNameFromDimensions([]byte(c.dimensions))
		if e != nil {
			t.Errorf("For %v, expected no error, got %v", c.dimensions, e)
		}
		if h != c.hostname {
			t.Errorf("For %v, expected hostname %v, got %v",
				c.dimensions, c.hostname, h)
		}
	}
}

func TestGetDutNameFromDimensionsErrors(t *testing.T) {
	t.Parallel()
	dimensions := []string{
		"{\"label-power\": [\"battery\"], \"environment\": [\"ENVIRONMENT_PROD\"]}",
		"",
	}

	for _, d := range dimensions {
		h, e := getDutNameFromDimensions([]byte(d))
		if e == nil {
			t.Errorf("For %v, expected an error, got hostname %v with no error", d, h)
		}
	}
}
