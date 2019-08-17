// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package enumeration

import (
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
)

// GetForTests returns the test metadata for specified tests.
func GetForTests(metadata *api.AutotestTestMetadata, tests []*test_platform.Request_Test) ([]*steps.EnumerationResponse_AutotestInvocation, error) {
	var invs []*steps.EnumerationResponse_AutotestInvocation
	autotestTests := metadata.GetTests()

	// TODO(akeshet): This loop is O(autotest test corpus size) * O(num requested tests).
	// It should be possible to optimize.
	for _, tr := range tests {
		switch h := tr.Harness.(type) {
		case *test_platform.Request_Test_Autotest_:
			for _, a := range autotestTests {
				if a.Name == h.Autotest.Name {
					invs = append(invs, &steps.EnumerationResponse_AutotestInvocation{
						Test:     a,
						TestArgs: h.Autotest.TestArgs,
					})
					// Autotest test names are unique, so bail out of searching
					// for other matches.
					break
				}
			}
		default:
			return nil, errors.Reason("unknown harness %+v", h).Err()
		}
	}

	return invs, nil
}

// GetForSuites returns the test metadata for specified suites.
func GetForSuites(metadata *api.AutotestTestMetadata, suites []*test_platform.Request_Suite) []*steps.EnumerationResponse_AutotestInvocation {
	sNames := suiteNames(suites)
	tNames := testsInSuites(metadata.GetSuites(), sNames)
	tests := filterTests(metadata.GetTests(), tNames)
	return wrapInAutotestInvocation(tests)
}

func filterTests(tests []*api.AutotestTest, keep stringset.Set) []*api.AutotestTest {
	ret := make([]*api.AutotestTest, 0, len(keep))
	for _, t := range tests {
		if keep.Has(t.GetName()) {
			ret = append(ret, t)
		}
	}
	return ret
}

func wrapInAutotestInvocation(tests []*api.AutotestTest) []*steps.EnumerationResponse_AutotestInvocation {
	ret := make([]*steps.EnumerationResponse_AutotestInvocation, 0, len(tests))
	for _, t := range tests {
		ret = append(ret, &steps.EnumerationResponse_AutotestInvocation{Test: t})
	}
	return ret
}

func testNames(ts []*test_platform.Request_Test) (stringset.Set, error) {
	ns := stringset.New(len(ts))
	for _, t := range ts {
		switch h := t.GetHarness().(type) {
		case *test_platform.Request_Test_Autotest_:
			ns.Add(h.Autotest.Name)
		default:
			return nil, errors.Reason("unknown harness %+v", h).Err()
		}
	}
	return ns, nil
}

func suiteNames(ss []*test_platform.Request_Suite) stringset.Set {
	ns := stringset.New(len(ss))
	for _, s := range ss {
		ns.Add(s.GetName())
	}
	return ns
}

func testsInSuites(ss []*api.AutotestSuite, sNames stringset.Set) stringset.Set {
	tNames := stringset.New(0)
	for _, s := range ss {
		if sNames.Has(s.GetName()) {
			tNames = tNames.Union(extractTestNames(s))
		}
	}
	return tNames

}

func extractTestNames(s *api.AutotestSuite) stringset.Set {
	tNames := stringset.New(len(s.GetTests()))
	for _, t := range s.GetTests() {
		tNames.Add(t.GetName())
	}
	return tNames
}
