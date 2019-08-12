// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package recipe formulates buildbucket requests for the cros_test_platform
// recipe, given arguments from the skylab tool.
package recipe

import (
	"net/url"
	"strings"
	"time"

	"github.com/golang/protobuf/ptypes"

	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/luci/common/errors"
)

// Args defines the arguments used to construct a cros_test_platform request.
type Args struct {
	SuiteNames []string
	TestNames  []string
	Model      string
	Image      string
	Board      string
	// Pool specifies the device pool to use. For managed pools, it can be
	// specified as a fully qualified name (e.g. "MANAGED_POOL_CQ"), a skylab
	// pool label value (e.g. "DUT_POOL_CQ"), or an autotest-style short name
	// (e.g. "cq"). If it doesn't match a managed pool in any of these forms,
	// then it will be mapped to an unmanaged pool.
	Pool                       string
	QuotaAccount               string
	Timeout                    time.Duration
	Keyvals                    map[string]string
	FreeformSwarmingDimensions []string
	AutotestTestArgs           string
	MaxRetries                 int
}

// Request constructs a cros_test_platform request from the given arguments.
func Request(a Args) (*test_platform.Request, error) {
	req := &test_platform.Request{}

	req.TestPlan = &test_platform.Request_TestPlan{}
	for _, suiteName := range a.SuiteNames {
		if a.AutotestTestArgs != "" {
			return nil, errors.Reason("cannot specify both autotest test args and suite").Err()
		}
		req.TestPlan.Suite = append(
			req.TestPlan.Suite,
			&test_platform.Request_Suite{Name: suiteName},
		)
	}
	for _, testName := range a.TestNames {
		ts := &test_platform.Request_Test{}
		ts.Harness = &test_platform.Request_Test_Autotest_{
			Autotest: &test_platform.Request_Test_Autotest{
				Name:     testName,
				TestArgs: a.AutotestTestArgs,
			},
		}
		req.TestPlan.Test = append(req.TestPlan.Test, ts)
	}

	req.Params = &test_platform.Request_Params{}
	params := req.Params

	model := a.Model
	// TODO(crbug.com/991591): The model inference from board is a temporary
	// workaround, that only works for non-unibuild requests. Once the traffic
	// split rules are modified to support model-agnostic requests, this
	// workaround should be removed.
	if model == "" {
		model = a.Board
	}
	params.HardwareAttributes = &test_platform.Request_Params_HardwareAttributes{
		Model: model,
	}

	params.Scheduling = toScheduling(a.Pool, a.QuotaAccount)

	params.SoftwareAttributes = &test_platform.Request_Params_SoftwareAttributes{
		BuildTarget: &chromiumos.BuildTarget{Name: a.Board},
	}

	params.SoftwareDependencies = []*test_platform.Request_Params_SoftwareDependency{
		{
			Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: a.Image},
		},
	}

	params.Decorations = &test_platform.Request_Params_Decorations{
		AutotestKeyvals: a.Keyvals,
	}

	params.FreeformAttributes = &test_platform.Request_Params_FreeformAttributes{
		SwarmingDimensions: a.FreeformSwarmingDimensions,
	}

	// TODO(akeshet): Make retry-allowance paramaterizable.
	params.Retry = &test_platform.Request_Params_Retry{
		Max:   int32(a.MaxRetries),
		Allow: a.MaxRetries != 0,
	}

	u := &url.URL{
		Scheme: "gs",
		Host:   "chromeos-image-archive",
		Path:   a.Image,
	}
	params.Metadata = &test_platform.Request_Params_Metadata{
		TestMetadataUrl: u.String(),
	}

	duration := ptypes.DurationProto(a.Timeout)
	params.Time = &test_platform.Request_Params_Time{
		MaximumDuration: duration,
	}

	return req, nil
}

func toScheduling(pool string, quotaAccount string) *test_platform.Request_Params_Scheduling {
	s := test_platform.Request_Params_Scheduling{}
	switch {
	case quotaAccount != "":
		s.Pool = &test_platform.Request_Params_Scheduling_QuotaAccount{QuotaAccount: quotaAccount}
	default:
		managedPool, isManaged := managedPool(pool)
		switch isManaged {
		case true:
			s.Pool = &test_platform.Request_Params_Scheduling_ManagedPool_{ManagedPool: managedPool}
		case false:
			s.Pool = &test_platform.Request_Params_Scheduling_UnmanagedPool{UnmanagedPool: pool}
		}
	}
	return &s
}

func managedPool(pool string) (test_platform.Request_Params_Scheduling_ManagedPool, bool) {
	if p, ok := test_platform.Request_Params_Scheduling_ManagedPool_value[pool]; ok {
		return test_platform.Request_Params_Scheduling_ManagedPool(p), true
	}
	mungedPool := strings.TrimPrefix(pool, "DUT_POOL_")
	mungedPool = strings.ToLower(mungedPool)
	if p, ok := nonstandardPoolNames[mungedPool]; ok {
		return p, true
	}
	return 0, false
}

var nonstandardPoolNames = map[string]test_platform.Request_Params_Scheduling_ManagedPool{
	"cq":            test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ,
	"bvt":           test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT,
	"suites":        test_platform.Request_Params_Scheduling_MANAGED_POOL_SUITES,
	"cts":           test_platform.Request_Params_Scheduling_MANAGED_POOL_CTS,
	"cts-perbuild":  test_platform.Request_Params_Scheduling_MANAGED_POOL_CTS_PERBUILD,
	"continuous":    test_platform.Request_Params_Scheduling_MANAGED_POOL_CONTINUOUS,
	"arc-presubmit": test_platform.Request_Params_Scheduling_MANAGED_POOL_ARC_PRESUBMIT,
	"quota":         test_platform.Request_Params_Scheduling_MANAGED_POOL_QUOTA,
}
