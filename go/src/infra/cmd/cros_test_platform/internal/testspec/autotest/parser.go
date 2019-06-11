// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/luci/common/errors"
)

func parseTestControl(text string) (*testMetadata, error) {
	var merr errors.MultiError
	var tm testMetadata
	merr = append(merr, parseTestName(text, &tm))
	merr = append(merr, parseSyncCount(text, &tm))
	merr = append(merr, parseRetries(text, &tm))
	merr = append(merr, parseDependencies(text, &tm))
	merr = append(merr, parseSuites(text, &tm))
	return &tm, unwrapMultiErrorIfNil(merr)
}

func parseSuiteControl(text string) (*api.AutotestSuite, error) {
	var merr errors.MultiError
	var as api.AutotestSuite
	merr = append(merr, parseSuiteName(text, &as))
	merr = append(merr, parseChildDependencies(text, &as))
	return &as, unwrapMultiErrorIfNil(merr)
}

func unwrapMultiErrorIfNil(merr errors.MultiError) error {
	if merr.First() == nil {
		return nil
	}
	return merr
}

func parseTestName(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, namePattern)
	var err error
	tm.Name, err = unwrapSingleSubmatchOrError(ms, "parseTestName")
	return err
}

func findMatchesInAllLines(text string, re *regexp.Regexp) [][]string {
	ms := [][]string{}
	for _, s := range strings.Split(text, "\n") {
		ms = append(ms, re.FindAllStringSubmatch(s, -1)...)
	}
	return ms
}

func unwrapSingleSubmatchOrError(values [][]string, errContext string) (string, error) {
	switch len(values) {
	case 0:
		return "", nil
	case 1:
		m := values[0]
		if len(m) != 2 {
			// Number of sub-matches is determined only by the regexp
			// definitions in this module.
			// Incorrect number of sub-matches is thus a programming error that
			// will cause a panic() on *every* successful match.
			panic(fmt.Sprintf("%s: match has %d submatches, want 1: %s", errContext, len(m), m[1:]))
		}
		return m[1], nil
	default:
		return "", fmt.Errorf("%s: more than one value: %s", errContext, values)
	}
}

func parseSyncCount(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, syncCountPattern)
	sc, err := unwrapSingleSubmatchOrError(ms, "parseSyncCount")
	if err != nil {
		return err
	}
	if sc == "" {
		return nil
	}
	tm.DutCount, err = parseInt32OrError(sc, "parseSyncCount")
	if tm.DutCount > 0 {
		tm.NeedsMultipleDuts = true
	}
	return err
}

func parseInt32OrError(sc string, errContext string) (int32, error) {
	dc, err := strconv.ParseInt(sc, 10, 32)
	if err != nil {
		return 0, errors.Annotate(err, errContext).Err()
	}
	return int32(dc), nil
}

func parseRetries(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, retriesPattern)
	sc, err := unwrapSingleSubmatchOrError(ms, "parseRetries")
	if err != nil {
		return err
	}
	if sc == "" {
		setDefaultRetries(tm)
		return nil
	}
	tm.MaxRetries, err = parseInt32OrError(sc, "parseRetries")
	if tm.MaxRetries > 0 {
		tm.AllowRetries = true
	}
	return err
}

func setDefaultRetries(tm *testMetadata) {
	tm.AllowRetries = true
	tm.MaxRetries = 1
}

func parseDependencies(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, dependenciesPattern)
	cl, err := unwrapSingleSubmatchOrError(ms, "parseDependencies")
	if err != nil {
		return err
	}
	for _, s := range splitAndTrimCommaList(cl) {
		tm.Dependencies = append(tm.Dependencies, &api.AutotestTaskDependency{Label: s})
	}
	return nil
}

func splitAndTrimCommaList(cl string) []string {
	ret := []string{}
	ss := strings.Split(cl, ",")
	for _, s := range ss {
		s = strings.Trim(s, " ")
		if s != "" {
			ret = append(ret, s)
		}
	}
	return ret
}

func parseSuites(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, attributesPattern)
	cl, err := unwrapSingleSubmatchOrError(ms, "parseSuites")
	if err != nil {
		return err
	}
	tm.Suites = findAndStripPrefixFromEach(splitAndTrimCommaList(cl), "suite:")
	return nil
}

func findAndStripPrefixFromEach(ss []string, prefix string) []string {
	ret := make([]string, 0, len(ss))
	for _, s := range ss {
		if strings.HasPrefix(s, prefix) {
			ret = append(ret, strings.TrimPrefix(s, prefix))
		}
	}
	return ret
}

func parseSuiteName(text string, as *api.AutotestSuite) error {
	ms := findMatchesInAllLines(text, namePattern)
	var err error
	as.Name, err = unwrapSingleSubmatchOrError(ms, "parseSuiteName")
	return err
}

func parseChildDependencies(text string, as *api.AutotestSuite) error {
	ms := findMatchesInAllLines(text, suiteDependenciesPattern)
	cl, err := unwrapSingleSubmatchOrError(ms, "parseChildDependencies")
	if err != nil {
		return err
	}
	for _, s := range splitAndTrimCommaList(cl) {
		as.ChildDependencies = append(as.ChildDependencies, &api.AutotestTaskDependency{Label: s})
	}
	return nil
}

var (
	namePattern              = regexp.MustCompile(`^\s*NAME\s*=\s*['"]([\w\.-]+)['"]\s*`)
	syncCountPattern         = regexp.MustCompile(`^\s*SYNC_COUNT\s*=\s*(\d+)\s*`)
	retriesPattern           = regexp.MustCompile(`^\s*JOB_RETRIES\s*=\s*(\d+)\s*`)
	dependenciesPattern      = regexp.MustCompile(`^\s*DEPENDENCIES\s*=\s*['"]([\s\w\.,:-]+)['"]\s*`)
	attributesPattern        = regexp.MustCompile(`^\s*ATTRIBUTES\s*=\s*['"]([\s\w\.,:-]+)['"]\s*`)
	suiteDependenciesPattern = regexp.MustCompile(`^\s*args_dict\s*\[\s*['"]suite_dependencies['"]\s*\]\s*=\s*['"]([\s\w\.,:-]+)['"]\s*`)
)
