// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"testing"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"

	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/migration/scheduler"
)

func TestTrafficSplitWithoutRulesReturnsError(t *testing.T) {
	trafficSplitConfig := trafficSplitWithRules(unmanagedPoolRule("lumpy", "lumpy", "toolchain", scheduler.Backend_BACKEND_AUTOTEST))
	var cases = []struct {
		Tag     string
		Request *test_platform.Request
	}{
		{
			Tag:     "mismatched model",
			Request: unmanagedPoolRequest("link", "", "toolchain"),
		},
		{
			Tag:     "mismatched build target",
			Request: unmanagedPoolRequest("", "link", "toolchain"),
		},
		{
			Tag:     "mismatched unmanaged pool",
			Request: unmanagedPoolRequest("", "lumpy", "performance"),
		},
	}
	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			_, err := determineTrafficSplit(
				&steps.SchedulerTrafficSplitRequest{
					Request: c.Request,
				},
				trafficSplitConfig,
			)
			if err == nil {
				t.Errorf("no error returned for missing rules")
			}
		})

	}

}

func TestTrafficSplitWithNoSchedulingReturnsError(t *testing.T) {
	_, err := determineTrafficSplit(
		&steps.SchedulerTrafficSplitRequest{
			Request: &test_platform.Request{
				Params: &test_platform.Request_Params{
					HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
						Model: "lumpy",
					},
				},
			},
		},
		trafficSplitWithRules(unmanagedPoolRule("lumpy", "lumpy", "toolchain", scheduler.Backend_BACKEND_AUTOTEST)),
	)
	if err == nil {
		t.Errorf("no error returned for request without scheduling")
	}
}
func TestTrafficSplit(t *testing.T) {
	var cases = []struct {
		Tag                 string
		TrafficSplitConfig  *scheduler.TrafficSplit
		Request             *test_platform.Request
		WantAutotestRequest *test_platform.Request
		WantSkylabRequest   *test_platform.Request
	}{
		{
			Tag:                 "(unmanaged pool, model) match for autotest",
			TrafficSplitConfig:  trafficSplitWithRules(unmanagedPoolRule("link", "link", "toolchain", scheduler.Backend_BACKEND_AUTOTEST)),
			Request:             unmanagedPoolRequest("link", "", "toolchain"),
			WantAutotestRequest: unmanagedPoolRequest("link", "", "toolchain"),
		},
		{
			Tag:                 "(unmanaged pool, buildTarget) match for autotest",
			TrafficSplitConfig:  trafficSplitWithRules(unmanagedPoolRule("link", "link", "toolchain", scheduler.Backend_BACKEND_AUTOTEST)),
			Request:             unmanagedPoolRequest("", "link", "toolchain"),
			WantAutotestRequest: unmanagedPoolRequest("", "link", "toolchain"),
		},
		{
			Tag:                "(unmanaged pool, model) match for skylab",
			TrafficSplitConfig: trafficSplitWithRules(unmanagedPoolRule("link", "link", "toolchain", scheduler.Backend_BACKEND_SKYLAB)),
			Request:            unmanagedPoolRequest("link", "", "toolchain"),
			WantSkylabRequest:  unmanagedPoolRequest("link", "", "toolchain"),
		},
		{
			Tag:                "(unmanaged pool, buildTarget) match for skylab",
			TrafficSplitConfig: trafficSplitWithRules(unmanagedPoolRule("link", "link", "toolchain", scheduler.Backend_BACKEND_SKYLAB)),
			Request:            unmanagedPoolRequest("", "link", "toolchain"),
			WantSkylabRequest:  unmanagedPoolRequest("", "link", "toolchain"),
		},
		{
			Tag: "(unmanaged pool, buildTarget) match for skylab for one of multiple rules",
			TrafficSplitConfig: trafficSplitWithRules(
				unmanagedPoolRule("link", "link", "toolchain", scheduler.Backend_BACKEND_SKYLAB),
				unmanagedPoolRule("link", "link", "performance", scheduler.Backend_BACKEND_AUTOTEST),
			),
			Request:           unmanagedPoolRequest("", "link", "toolchain"),
			WantSkylabRequest: unmanagedPoolRequest("", "link", "toolchain"),
		},
		{
			Tag:                 "(managed pool, model) match for autotest",
			TrafficSplitConfig:  trafficSplitWithRules(managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT, scheduler.Backend_BACKEND_AUTOTEST)),
			Request:             managedPoolRequest("link", "", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
			WantAutotestRequest: managedPoolRequest("link", "", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
		},
		{
			Tag:                 "(managed pool, buildTarget) match for autotest",
			TrafficSplitConfig:  trafficSplitWithRules(managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT, scheduler.Backend_BACKEND_AUTOTEST)),
			Request:             managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
			WantAutotestRequest: managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
		},
		{
			Tag:                "(managed pool, model) match for skylab",
			TrafficSplitConfig: trafficSplitWithRules(managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT, scheduler.Backend_BACKEND_SKYLAB)),
			Request:            managedPoolRequest("link", "", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
			WantSkylabRequest:  managedPoolRequest("link", "", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
		},
		{
			Tag:                "(managed pool, buildTarget) match for skylab",
			TrafficSplitConfig: trafficSplitWithRules(managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT, scheduler.Backend_BACKEND_SKYLAB)),
			Request:            managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
			WantSkylabRequest:  managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
		},
		{
			Tag: "(managed pool, buildTarget) match for skylab for one of multiple rules",
			TrafficSplitConfig: trafficSplitWithRules(
				managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT, scheduler.Backend_BACKEND_SKYLAB),
				managedPoolRule("link", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ, scheduler.Backend_BACKEND_AUTOTEST),
			),
			Request:           managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
			WantSkylabRequest: managedPoolRequest("", "link", test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT),
		},
		{
			Tag: "(quota account, model, buildTarget) match for skylab for one of multiple rules",
			TrafficSplitConfig: trafficSplitWithRules(
				quotaAccountRule("link", "link", "cq", scheduler.Backend_BACKEND_SKYLAB),
				quotaAccountRule("link", "link", "bvt", scheduler.Backend_BACKEND_AUTOTEST),
			),
			Request:           quotaAccountRequest("link", "link", "cq"),
			WantSkylabRequest: quotaAccountRequest("link", "link", "cq"),
		},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			resp, err := determineTrafficSplit(
				&steps.SchedulerTrafficSplitRequest{
					Request: c.Request,
				},
				c.TrafficSplitConfig,
			)
			if err != nil {
				t.Fatalf("error in determineTrafficSplit: %s", err)
			}
			if diff := pretty.Compare(c.WantAutotestRequest, resp.AutotestRequest); diff != "" {
				t.Errorf("Incorrect autotest request, -want, +got: %s", diff)
			}
			if diff := pretty.Compare(c.WantSkylabRequest, resp.SkylabRequest); diff != "" {
				t.Errorf("Incorrect skylab request, -want, +got: %s", diff)
			}
		})
	}
}

func trafficSplitWithRules(rules ...*scheduler.Rule) *scheduler.TrafficSplit {
	return &scheduler.TrafficSplit{
		Rules: rules,
	}
}

func unmanagedPoolRule(model, buildTarget, pool string, backend scheduler.Backend) *scheduler.Rule {
	r := ruleSansPool(model, buildTarget, backend)
	r.Request.Scheduling = &test_platform.Request_Params_Scheduling{
		Pool: &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: pool},
	}
	return r
}

func ruleSansPool(model, buildTarget string, backend scheduler.Backend) *scheduler.Rule {
	return &scheduler.Rule{
		Request: &scheduler.Request{
			Model:       model,
			BuildTarget: &chromiumos.BuildTarget{Name: buildTarget},
		},
		Backend: backend,
	}
}

// The created Request includes model and buildTarget only if non-empty.
func unmanagedPoolRequest(model, buildTarget, pool string) *test_platform.Request {
	r := test_platform.Request{
		Params: &test_platform.Request_Params{
			Scheduling: &test_platform.Request_Params_Scheduling{
				Pool: &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: pool},
			},
		},
	}
	setRequestParamsIfNonEmpty(&r, model, buildTarget)
	return &r
}

func setRequestParamsIfNonEmpty(r *test_platform.Request, model, buildTarget string) {
	if model != "" {
		r.Params.HardwareAttributes = &test_platform.Request_Params_HardwareAttributes{
			Model: model,
		}
	}
	if buildTarget != "" {
		r.Params.SoftwareAttributes = &test_platform.Request_Params_SoftwareAttributes{
			BuildTarget: &chromiumos.BuildTarget{Name: buildTarget},
		}
	}
}

func managedPoolRule(model, buildTarget string, pool test_platform.Request_Params_Scheduling_ManagedPool, backend scheduler.Backend) *scheduler.Rule {
	r := ruleSansPool(model, buildTarget, backend)
	r.Request.Scheduling = &test_platform.Request_Params_Scheduling{
		Pool: &test_platform.Request_Params_Scheduling_ManagedPool_{
			ManagedPool: pool,
		},
	}
	return r
}

// The created Request includes model and buildTarget only if non-empty.
func managedPoolRequest(model, buildTarget string, pool test_platform.Request_Params_Scheduling_ManagedPool) *test_platform.Request {
	r := test_platform.Request{
		Params: &test_platform.Request_Params{
			Scheduling: &test_platform.Request_Params_Scheduling{
				Pool: &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: pool},
			},
		},
	}
	setRequestParamsIfNonEmpty(&r, model, buildTarget)
	return &r
}

func quotaAccountRule(model, buildTarget, account string, backend scheduler.Backend) *scheduler.Rule {
	r := ruleSansPool(model, buildTarget, backend)
	r.Request.Scheduling = &test_platform.Request_Params_Scheduling{
		Pool: &test_platform.Request_Params_Scheduling_QuotaAccount{QuotaAccount: account},
	}
	return r
}

// The created Request includes model and buildTarget only if non-empty.
func quotaAccountRequest(model, buildTarget, account string) *test_platform.Request {
	r := test_platform.Request{
		Params: &test_platform.Request_Params{
			Scheduling: &test_platform.Request_Params_Scheduling{
				Pool: &test_platform.Request_Params_Scheduling_QuotaAccount{QuotaAccount: account},
			},
		},
	}
	setRequestParamsIfNonEmpty(&r, model, buildTarget)
	return &r
}
