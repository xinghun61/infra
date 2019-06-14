// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package enumeration_test

import (
	"testing"

	"infra/cmd/cros_test_platform/internal/enumeration"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/luci/common/data/stringset"
)

func TestGetForTests(t *testing.T) {
	var cases = []struct {
		request string
		want    stringset.Set
	}{
		{"selected", stringset.NewFromSlice("selected")},
		{"non_existent", stringset.New(0)},
	}

	m := &api.AutotestTestMetadata{}
	addTestMetadata(m, "ignored", "selected")
	for _, c := range cases {
		t.Run(c.request, func(t *testing.T) {
			tests := enumeration.GetForTests(m, []*test_platform.Request_Test{{Name: c.request}})
			got := extractTestNames(tests)
			if diff := pretty.Compare(c.want, got); diff != "" {
				t.Errorf("enumerated tests differ, -want +got: %s", diff)
			}
		})
	}
}

// addTestMetadata adds tests to m with given names.
func addTestMetadata(m *api.AutotestTestMetadata, tNames ...string) {
	for _, t := range tNames {
		m.Tests = append(m.Tests, &api.AutotestTest{Name: t})
	}
}

func extractTestNames(ts []*api.AutotestTest) stringset.Set {
	ns := make([]string, 0, len(ts))
	for _, t := range ts {
		ns = append(ns, t.GetName())
	}
	return stringset.NewFromSlice(ns...)
}

func TestGetForSuites(t *testing.T) {
	var cases = []struct {
		tag      string
		metadata *api.AutotestTestMetadata
		request  []*test_platform.Request_Suite
		want     stringset.Set
	}{
		{
			tag: "select single suite",
			metadata: autotestMetadata(
				[]string{"included", "ignored"},
				map[string][]string{
					"selected":   {"included"},
					"unselected": {"ignored"},
				},
			),
			request: suiteRequest("selected"),
			want:    stringset.NewFromSlice("included"),
		},
		{
			tag: "select both suite",
			metadata: autotestMetadata(
				[]string{"included", "another_included"},
				map[string][]string{
					"selected":         {"included"},
					"another_selected": {"another_included"},
				},
			),
			request: suiteRequest("selected", "another_selected"),
			want:    stringset.NewFromSlice("included", "another_included"),
		},
		{
			tag: "select suite with missing test",
			metadata: autotestMetadata(
				[]string{},
				map[string][]string{
					"selected": {"missing"},
				},
			),
			request: suiteRequest("selected"),
			want:    stringset.New(0),
		},
	}

	for _, c := range cases {
		t.Run(c.tag, func(t *testing.T) {
			tests := enumeration.GetForSuites(c.metadata, c.request)
			got := extractTestNames(tests)
			if diff := pretty.Compare(c.want, got); diff != "" {
				t.Errorf("enumerated tests differ, -want +got: %s", diff)
			}
		})
	}
}

func suiteRequest(ns ...string) []*test_platform.Request_Suite {
	req := make([]*test_platform.Request_Suite, 0, len(ns))
	for _, n := range ns {
		req = append(req, &test_platform.Request_Suite{Name: n})
	}
	return req
}

// autotestMetadata creates a new AutotestTestMetadata containing tests with
// specified names and suites with specified names and contained tests.
func autotestMetadata(tests []string, suites map[string][]string) *api.AutotestTestMetadata {
	m := &api.AutotestTestMetadata{}
	addTestMetadata(m, tests...)
	for s, ts := range suites {
		addSuiteMetadata(m, s, ts...)
	}
	return m
}

// addSuiteMetadata adds a suite to m named sName and including tests named tNames.
func addSuiteMetadata(m *api.AutotestTestMetadata, sName string, tNames ...string) {
	suite := &api.AutotestSuite{Name: sName}
	for _, tName := range tNames {
		suite.Tests = append(suite.Tests, &api.AutotestSuite_TestReference{Name: tName})
	}
	m.Suites = append(m.Suites, suite)
}