// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package enumeration

import (
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/luci/common/data/stringset"
)

// GetForTests returns the test metadata for specified tests.
func GetForTests(metadata *api.AutotestTestMetadata, tests []*test_platform.Request_Test) []*api.AutotestTest {
	tNames := testNames(tests)
	return testsByName(metadata.GetTests(), tNames)
}

// GetForSuites returns the test metadata for specified suites.
func GetForSuites(metadata *api.AutotestTestMetadata, suites []*test_platform.Request_Suite) []*api.AutotestTest {
	sNames := suiteNames(suites)
	tNames := testsInSuites(metadata.GetSuites(), sNames)
	return testsByName(metadata.GetTests(), tNames)
}

func testsByName(tests []*api.AutotestTest, names stringset.Set) []*api.AutotestTest {
	ret := make([]*api.AutotestTest, 0, len(names))
	for _, t := range tests {
		if names.Has(t.GetName()) {
			ret = append(ret, t)
		}
	}
	return ret
}

func testNames(ts []*test_platform.Request_Test) stringset.Set {
	ns := stringset.New(len(ts))
	for _, t := range ts {
		ns.Add(t.GetName())
	}
	return ns
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
