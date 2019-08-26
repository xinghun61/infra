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

// NewTestPlanForSuites returns a test plan consisting of the given named suites.
func NewTestPlanForSuites(suiteNames ...string) *test_platform.Request_TestPlan {
	p := test_platform.Request_TestPlan{}
	for _, s := range suiteNames {
		p.Suite = append(p.Suite, &test_platform.Request_Suite{Name: s})
	}
	return &p
}

// NewTestPlanForAutotestTests returns a test plan consisting of the given named autotest tests.
func NewTestPlanForAutotestTests(autotestArgs string, testNames ...string) *test_platform.Request_TestPlan {
	p := test_platform.Request_TestPlan{}
	for _, t := range testNames {
		p.Test = append(p.Test, &test_platform.Request_Test{
			Harness: &test_platform.Request_Test_Autotest_{
				Autotest: &test_platform.Request_Test_Autotest{
					Name:     t,
					TestArgs: autotestArgs,
				},
			},
		})
	}
	return &p
}

// Args defines the arguments used to construct a cros_test_platform request.
type Args struct {
	TestPlan *test_platform.Request_TestPlan

	Model string
	// This Image argument is interpreted as a ChromeOS image version, and used
	// to construct both a provisionable dimension and test metadata url.
	Image string
	Board string
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
	Priority                   int64
	Tags                       []string
	ProvisionLabels            []string
}

// TestPlatformRequest constructs a cros_test_platform.Request from Args.
func (a *Args) TestPlatformRequest() (*test_platform.Request, error) {
	req := &test_platform.Request{
		TestPlan: a.TestPlan,
	}

	req.Params = &test_platform.Request_Params{}
	params := req.Params

	params.HardwareAttributes = &test_platform.Request_Params_HardwareAttributes{
		Model: a.Model,
	}

	params.Scheduling = toScheduling(a.Pool, a.QuotaAccount, a.Priority)

	params.SoftwareAttributes = &test_platform.Request_Params_SoftwareAttributes{
		BuildTarget: &chromiumos.BuildTarget{Name: a.Board},
	}

	var deps []*test_platform.Request_Params_SoftwareDependency
	if a.Image != "" {
		deps = append(deps, &test_platform.Request_Params_SoftwareDependency{
			Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: a.Image},
		})
	}
	for _, label := range a.ProvisionLabels {
		dep, err := toSoftwareDependency(label)
		if err != nil {
			return nil, err
		}
		deps = append(deps, dep)
	}
	params.SoftwareDependencies = deps

	params.Decorations = &test_platform.Request_Params_Decorations{
		AutotestKeyvals: a.Keyvals,
		Tags:            a.Tags,
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

func toScheduling(pool string, quotaAccount string, priority int64) *test_platform.Request_Params_Scheduling {
	s := test_platform.Request_Params_Scheduling{Priority: priority}
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

func toSoftwareDependency(provisionableLabel string) (*test_platform.Request_Params_SoftwareDependency, error) {
	parts := strings.Split(provisionableLabel, ":")
	if len(parts) != 2 {
		return nil, errors.Reason("invalid provisionable label %s", provisionableLabel).Err()
	}
	prefix := parts[0]
	value := parts[1]
	dep := &test_platform.Request_Params_SoftwareDependency{}
	switch prefix {
	// These prefixes are interpreted by autotest's provisioning behavior;
	// they are defined in the autotest repo, at utils/labellib.py
	case "cros-version":
		dep.Dep = &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{
			ChromeosBuild: value,
		}
	case "fwro-version":
		dep.Dep = &test_platform.Request_Params_SoftwareDependency_RoFirmwareBuild{
			RoFirmwareBuild: value,
		}
	case "fwrw-version":
		dep.Dep = &test_platform.Request_Params_SoftwareDependency_RwFirmwareBuild{
			RwFirmwareBuild: value,
		}
	default:
		return nil, errors.Reason("invalid provisionable label prefix %s", prefix).Err()
	}
	return dep, nil
}
