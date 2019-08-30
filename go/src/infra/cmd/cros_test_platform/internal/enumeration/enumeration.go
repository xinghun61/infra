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
	tNames, err := testNames(tests)
	if err != nil {
		return nil, err
	}
	ts := testsByName(filterTests(metadata.GetTests(), tNames))

	var invs []*steps.EnumerationResponse_AutotestInvocation
	for _, tr := range tests {
		// Any tests of incorrect type would already be caught by testNames()
		// above. Better panic in case of failure here.
		h := tr.Harness.(*test_platform.Request_Test_Autotest_)
		if t, ok := ts[h.Autotest.Name]; ok {
			invs = append(invs, &steps.EnumerationResponse_AutotestInvocation{
				Test:        t,
				TestArgs:    h.Autotest.TestArgs,
				DisplayName: h.Autotest.DisplayName,
			})
		}
	}
	return invs, nil
}

// GetForSuites returns the test metadata for specified suites.
func GetForSuites(metadata *api.AutotestTestMetadata, suites []*test_platform.Request_Suite) []*steps.EnumerationResponse_AutotestInvocation {
	invs := []*steps.EnumerationResponse_AutotestInvocation{}
	for _, sName := range suiteNames(suites) {
		tNames := testsInSuite(metadata.GetSuites(), sName)
		tests := filterTests(metadata.GetTests(), tNames)
		invs = append(invs, autotestInvocationsForSuite(sName, tests)...)
	}
	return invs
}

// GetForEnumeration marshals the provided pre-enumerated tests into standard
// enumeration response format.
func GetForEnumeration(enumeration *test_platform.Request_Enumeration) []*steps.EnumerationResponse_AutotestInvocation {
	ret := make([]*steps.EnumerationResponse_AutotestInvocation, 0, len(enumeration.GetAutotestInvocations()))
	for _, t := range enumeration.GetAutotestInvocations() {
		ret = append(ret, &steps.EnumerationResponse_AutotestInvocation{
			Test:          t.GetTest(),
			TestArgs:      t.GetTestArgs(),
			DisplayName:   t.GetDisplayName(),
			ResultKeyvals: t.GetResultKeyvals(),
		})
	}
	return ret
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

func testsByName(tests []*api.AutotestTest) map[string]*api.AutotestTest {
	ret := make(map[string]*api.AutotestTest)
	for _, t := range tests {
		ret[t.GetName()] = t
	}
	return ret
}

func autotestInvocationsForSuite(sName string, tests []*api.AutotestTest) []*steps.EnumerationResponse_AutotestInvocation {
	ret := make([]*steps.EnumerationResponse_AutotestInvocation, 0, len(tests))
	for _, t := range tests {
		ret = append(ret, &steps.EnumerationResponse_AutotestInvocation{
			Test: t,
			ResultKeyvals: map[string]string{
				"suite": sName,
			},
		})
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

func suiteNames(ss []*test_platform.Request_Suite) []string {
	ns := stringset.New(len(ss))
	for _, s := range ss {
		ns.Add(s.GetName())
	}
	return ns.ToSlice()
}

func testsInSuite(ss []*api.AutotestSuite, sName string) stringset.Set {
	tNames := stringset.New(0)
	for _, s := range ss {
		if s.GetName() == sName {
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
