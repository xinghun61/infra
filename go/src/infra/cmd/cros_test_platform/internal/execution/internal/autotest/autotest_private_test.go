// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
)

func TestToPool(t *testing.T) {
	Convey("Given scheduling parameters with ", t, func() {
		cases := []struct {
			name        string
			scheduling  *test_platform.Request_Params_Scheduling
			expectPool  string
			expectError bool
		}{
			{
				name: "an unmanaged pool",
				scheduling: &test_platform.Request_Params_Scheduling{
					Pool: &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: "foo-pool"},
				},
				expectPool: "foo-pool",
			},
			{
				name: "a managed pool",
				scheduling: &test_platform.Request_Params_Scheduling{
					Pool: &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ},
				},
				expectPool: "cq",
			},
			{
				name: "the quota pool",
				scheduling: &test_platform.Request_Params_Scheduling{
					Pool: &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: test_platform.Request_Params_Scheduling_MANAGED_POOL_QUOTA},
				},
				expectError: true,
			},
			{
				name: "a quota account",
				scheduling: &test_platform.Request_Params_Scheduling{
					Pool: &test_platform.Request_Params_Scheduling_QuotaAccount{QuotaAccount: "foo-account"},
				},
				expectError: true,
			},
		}
		for _, c := range cases {
			Convey(c.name, func() {
				pool, err := toPool(c.scheduling)
				Convey("then correct pool string and error are returned.", func() {
					So(pool, ShouldEqual, c.expectPool)
					So(err != nil, ShouldEqual, c.expectError)
				})
			})
		}
	})

}

func TestPriorityConversion(t *testing.T) {
	var cases = []struct {
		Tag      string
		Skylab   int64
		Autotest int
	}{
		{Tag: "clip_above", Skylab: 0, Autotest: 80},
		{Tag: "clip_below", Skylab: 300, Autotest: 10},
		{Tag: "convert_default", Skylab: 140, Autotest: 40},
	}
	for _, c := range cases {
		t.Run(fmt.Sprintf("convert_%d", c.Skylab), func(t *testing.T) {
			got := toAutotestPriority(c.Skylab)
			if c.Autotest != got {
				t.Errorf("toAutotestPriority(%d) - want %d got %d", c.Skylab, c.Autotest, got)
			}
		})
	}
}
