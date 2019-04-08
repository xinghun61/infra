// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"testing"
	"time"
)

func TestRelativeTime_Set(t *testing.T) {
	t.Parallel()
	now := time.Date(2000, 1, 2, 3, 4, 5, 6, time.UTC)
	nowFunc := func() time.Time { return now }
	cases := []struct {
		desc  string
		input string
		want  time.Time
	}{
		{
			desc:  "positive",
			input: "5",
			want:  time.Date(2000, 1, 7, 3, 4, 5, 6, time.UTC),
		},
		{
			desc:  "positive with plus",
			input: "+5",
			want:  time.Date(2000, 1, 7, 3, 4, 5, 6, time.UTC),
		},
		{
			desc:  "negative",
			input: "-4",
			want:  time.Date(1999, 12, 29, 3, 4, 5, 6, time.UTC),
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			var got time.Time
			f := RelativeTime{T: &got, now: nowFunc}
			if err := f.Set(c.input); err != nil {
				t.Fatalf("Set(%#v) returned error: %s", c.input, err)
			}
			if !got.Equal(c.want) {
				t.Errorf("Set(%#v) = %s; want %s", c.input, got.String(), c.want.String())
			}
		})
	}
}
