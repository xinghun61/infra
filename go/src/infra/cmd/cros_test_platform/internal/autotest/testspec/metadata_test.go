// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"fmt"
	"io"
	"strings"
	"testing"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/luci/common/errors"
)

func TestGetReturnsPartialResults(t *testing.T) {
	fl := newFakeLoader()
	fl.AddSuites([]string{"suite", "non_existent_suite"})
	fl.AddTests([]string{"test", "non_existent_test"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{
		"test": testWithNameAndSuites("test", []string{}),
	})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{
		"suite": {Name: "suite"},
	})
	g := getter{fl, ft, fs}
	resp, err := g.Get("ignored")
	if err == nil {
		t.Errorf("getter.Get() did not report parse failures")
	}

	wantTests := []string{"test"}
	gotTests := []string{}
	for _, t := range resp.GetAutotest().GetTests() {
		gotTests = append(gotTests, t.Name)
	}
	if diff := pretty.Compare(wantTests, gotTests); diff != "" {
		t.Errorf("Tests differ, -want +got, %s", diff)
	}

	wantSuites := []string{"suite"}
	gotSuites := []string{}
	for _, s := range resp.GetAutotest().GetSuites() {
		gotSuites = append(gotSuites, s.Name)
	}
	if diff := pretty.Compare(wantSuites, gotSuites); diff != "" {
		t.Errorf("Suites differ, -want +got, %s", diff)
	}
}

func TestGetSuiteWithoutTests(t *testing.T) {
	fl := newFakeLoader()
	fl.AddSuites([]string{"suite"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{
		"suite": {Name: "suite"},
	})
	g := getter{fl, ft, fs}
	resp, err := g.Get("ignored")
	if err != nil {
		t.Fatalf("getter.Get(): %s", err)
	}
	want := map[string][]string{"suite": {}}
	got := extractSuiteTests(resp.GetAutotest().GetSuites())
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Suite.Tests differ, -want +got, %s", diff)
	}
}

func TestGetSuiteWithOneTest(t *testing.T) {
	fl := newFakeLoader()
	fl.AddTests([]string{"test"})
	fl.AddSuites([]string{"suite"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{
		"test": testWithNameAndSuites("test", []string{"suite"}),
	})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{
		"suite": {Name: "suite"},
	})
	g := getter{fl, ft, fs}
	resp, err := g.Get("root")
	if err != nil {
		t.Fatalf("getter.Get(): %s", err)
	}
	want := map[string][]string{"suite": {"test"}}
	got := extractSuiteTests(resp.GetAutotest().GetSuites())
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Suite.Tests differ, -want +got, %s", diff)
	}
}

func TestGetSuiteWithTwoTests(t *testing.T) {
	fl := newFakeLoader()
	fl.AddTests([]string{"test1", "test2"})
	fl.AddSuites([]string{"suite"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{
		"test1": testWithNameAndSuites("test1", []string{"suite"}),
		"test2": testWithNameAndSuites("test2", []string{"suite"}),
	})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{
		"suite": {Name: "suite"},
	})
	g := getter{fl, ft, fs}
	resp, err := g.Get("root")
	if err != nil {
		t.Fatalf("getter.Get(): %s", err)
	}
	want := map[string][]string{"suite": {"test1", "test2"}}
	got := extractSuiteTests(resp.GetAutotest().GetSuites())
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Suite.Tests differ, -want +got, %s", diff)
	}
}

func TestGetTwoSuitesWithSameTest(t *testing.T) {
	fl := newFakeLoader()
	fl.AddTests([]string{"test"})
	fl.AddSuites([]string{"suite1", "suite2"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{
		"test": testWithNameAndSuites("test", []string{"suite1", "suite2"}),
	})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{
		"suite1": {Name: "suite1"},
		"suite2": {Name: "suite2"},
	})
	g := getter{fl, ft, fs}
	resp, err := g.Get("root")
	if err != nil {
		t.Fatalf("getter.Get(): %s", err)
	}
	want := map[string][]string{
		"suite1": {"test"},
		"suite2": {"test"},
	}
	got := extractSuiteTests(resp.GetAutotest().GetSuites())
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Suite.Tests differ, -want +got, %s", diff)
	}
}

func TestGetTestInNonExistentSuite(t *testing.T) {
	fl := newFakeLoader()
	fl.AddTests([]string{"test"})
	ft := newFakeParseTestControlFn(map[string]*testMetadata{
		"test": testWithNameAndSuites("test", []string{"non_existent_suite"}),
	})
	fs := newFakeParseSuiteControlFn(map[string]*api.AutotestSuite{})
	g := getter{fl, ft, fs}
	resp, err := g.Get("ignored")
	if err != nil {
		t.Fatalf("getter.Get(): %s", err)
	}
	want := map[string][]string{}
	got := extractSuiteTests(resp.GetAutotest().GetSuites())
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Suite.Tests differ, -want +got, %s", diff)
	}
}

// newFakeParseTestControlFn returns a fake parseTestControlFn that returns
// canned parse results.
//
// canned must map *contents of the control file* to their parse results. The
// returned parseTestControlFn returns error for any control file not in canned.
func newFakeParseTestControlFn(canned map[string]*testMetadata) parseTestControlFn {
	return func(text string) (*testMetadata, error) {
		tm, ok := canned[text]
		if !ok {
			return nil, errors.Reason("uncanned control file: %s", text).Err()
		}
		return tm, nil
	}
}

func testWithNameAndSuites(name string, suites []string) *testMetadata {
	return &testMetadata{
		AutotestTest: api.AutotestTest{
			Name: name,
		},
		Suites: suites,
	}
}

// newFakeParseSuiteControlFn returns a fake parseSuiteControlFn that returns
// canned parse results.
//
// canned must map *contents of the control file* to their parse results. The
// returned parseSuiteControlFn returns error for any control file not in
// canned.
func newFakeParseSuiteControlFn(canned map[string]*api.AutotestSuite) parseSuiteControlFn {
	return func(text string) (*api.AutotestSuite, error) {
		as, ok := canned[text]
		if !ok {
			return nil, errors.Reason("uncanned control file: %s", text).Err()
		}
		return as, nil
	}
}

func newFakeLoader() *fakeLoader {
	return &fakeLoader{
		tests:  make(map[string]io.Reader),
		suites: make(map[string]io.Reader),
	}
}

type fakeLoader struct {
	tests      map[string]io.Reader
	suites     map[string]io.Reader
	pathSuffix int
}

// AddTests adds the given texts as a test new control files at  arbitrary
// paths.
func (d *fakeLoader) AddTests(texts []string) {
	for _, t := range texts {
		d.tests[fmt.Sprintf("test%d", d.pathSuffix)] = strings.NewReader(t)
		d.pathSuffix++
	}
}

// RegisterSuite adds the given texts as a new suite control files at arbitrary
// paths.
func (d *fakeLoader) AddSuites(texts []string) {
	for _, t := range texts {
		d.suites[fmt.Sprintf("test%d", d.pathSuffix)] = strings.NewReader(t)
		d.pathSuffix++
	}
}

func (d *fakeLoader) Discover(string) error {
	return nil
}

func (d *fakeLoader) Tests() map[string]io.Reader {
	return d.tests
}

func (d *fakeLoader) Suites() map[string]io.Reader {
	return d.suites
}

func extractTestNames(tests []*api.AutotestTest) []string {
	m := make([]string, 0, len(tests))
	for _, t := range tests {
		m = append(m, t.Name)
	}
	return m
}

func extractSuiteNames(suites []*api.AutotestSuite) []string {
	m := make([]string, 0, len(suites))
	for _, s := range suites {
		m = append(m, s.Name)
	}
	return m
}

func extractSuiteTests(suites []*api.AutotestSuite) map[string][]string {
	m := make(map[string][]string)
	for _, s := range suites {
		ts := []string{}
		for _, t := range s.GetTests() {
			ts = append(ts, t.Name)
		}
		m[s.Name] = ts
	}
	return m
}
