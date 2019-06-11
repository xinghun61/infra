// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import (
	"io"
	"io/ioutil"
	"sort"

	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/luci/common/errors"
)

// Get computes metadata for all test and suite control files
// found within the directory tree rooted at root.
//
// Get always returns a valid api.TestMetadataResponse. In case of
// errors, the returned metadata corredsponds to the successfully parsed
// control files.
func Get(root string) (*api.TestMetadataResponse, error) {
	g := getter{
		controlFileLoader:   &controlFilesLoaderImpl{},
		parseTestControlFn:  parseTestControl,
		parseSuiteControlFn: parseSuiteControl,
	}
	return g.Get(root)
}

type controlFileLoader interface {
	Discover(string) error
	Tests() map[string]io.Reader
	Suites() map[string]io.Reader
}

type testMetadata struct {
	api.AutotestTest
	Suites []string
}
type parseTestControlFn func(string) (*testMetadata, error)
type parseSuiteControlFn func(string) (*api.AutotestSuite, error)

type getter struct {
	controlFileLoader   controlFileLoader
	parseTestControlFn  parseTestControlFn
	parseSuiteControlFn parseSuiteControlFn
}

func (g *getter) Get(root string) (*api.TestMetadataResponse, error) {
	if err := g.controlFileLoader.Discover(root); err != nil {
		return nil, errors.Annotate(err, "get autotest metadata").Err()
	}

	var merr errors.MultiError
	tests, err := g.parseTests(g.controlFileLoader.Tests())
	merr = append(merr, err)
	suites, err := g.parseSuites(g.controlFileLoader.Suites())
	merr = append(merr, err)

	collectTestsInSuites(tests, suites)
	sortTestsInSuites(suites)
	return &api.TestMetadataResponse{
		Autotest: &api.AutotestTestMetadata{
			Suites: suites,
			Tests:  extractAutotestTests(tests),
		},
	}, unwrapMultiErrorIfNil(merr)
}

func (g *getter) parseTests(controls map[string]io.Reader) ([]*testMetadata, error) {
	var merr errors.MultiError
	tests := make([]*testMetadata, 0, len(controls))
	for _, t := range controls {
		bt, err := ioutil.ReadAll(t)
		if err != nil {
			merr = append(merr, errors.Annotate(err, "parse tests").Err())
			continue
		}
		tm, err := g.parseTestControlFn(string(bt))
		if err != nil {
			merr = append(merr, errors.Annotate(err, "parse tests").Err())
			continue
		}
		tests = append(tests, tm)
	}
	return tests, unwrapMultiErrorIfNil(merr)
}

func (g *getter) parseSuites(controls map[string]io.Reader) ([]*api.AutotestSuite, error) {
	var merr errors.MultiError
	suites := make([]*api.AutotestSuite, 0, len(controls))
	for _, t := range controls {
		bt, err := ioutil.ReadAll(t)
		if err != nil {
			merr = append(merr, errors.Annotate(err, "parse tests").Err())
			continue
		}
		sm, err := g.parseSuiteControlFn(string(bt))
		if err != nil {
			merr = append(merr, errors.Annotate(err, "parse suites").Err())
			continue
		}
		suites = append(suites, sm)
	}
	return suites, unwrapMultiErrorIfNil(merr)
}

func collectTestsInSuites(tests []*testMetadata, suites []*api.AutotestSuite) {
	sm := make(map[string]*api.AutotestSuite)
	for _, s := range suites {
		sm[s.GetName()] = s
	}
	for _, t := range tests {
		for _, s := range t.Suites {
			appendTestToSuite(t, sm[s])
		}
	}
}

func sortTestsInSuites(suites []*api.AutotestSuite) {
	for _, s := range suites {
		sort.SliceStable(s.Tests, func(i, j int) bool {
			return s.Tests[i].Name < s.Tests[j].Name
		})
	}
}

func appendTestToSuite(test *testMetadata, suite *api.AutotestSuite) {
	suite.Tests = append(suite.Tests, &api.AutotestSuite_TestReference{Name: test.GetName()})

}

func extractAutotestTests(tests []*testMetadata) []*api.AutotestTest {
	at := make([]*api.AutotestTest, 0, len(tests))
	for _, t := range tests {
		at = append(at, &t.AutotestTest)
	}
	return at
}
