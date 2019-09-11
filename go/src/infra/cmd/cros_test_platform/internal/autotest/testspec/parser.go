// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

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
	parseTestName(text, &tm)
	parseExecutionEnvironment(text, &tm)
	merr = append(merr, parseSyncCount(text, &tm))
	merr = append(merr, parseRetries(text, &tm))
	merr = append(merr, parseDependencies(text, &tm))
	parseSuites(text, &tm)
	return &tm, unwrapMultiErrorIfNil(merr)
}

func parseSuiteControl(text string) (*api.AutotestSuite, error) {
	var as api.AutotestSuite
	parseSuiteName(text, &as)
	parseChildDependencies(text, &as)
	return &as, nil
}

func unwrapMultiErrorIfNil(merr errors.MultiError) error {
	if merr.First() == nil {
		return nil
	}
	return merr
}

func parseTestName(text string, tm *testMetadata) {
	ms := findMatchesInAllLines(text, namePattern)
	tm.Name, _ = stripMatchingQuotes(unwrapLastSubmatch(ms, "parseTestName"))
}

func parseExecutionEnvironment(text string, tm *testMetadata) {
	ms := findMatchesInAllLines(text, testTypePattern)
	env, _ := stripMatchingQuotes(unwrapLastSubmatch(ms, "parseExecutionEnvironment"))
	env = strings.ToLower(env)
	switch env {
	case "client":
		tm.ExecutionEnvironment = api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT
	case "server":
		tm.ExecutionEnvironment = api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER
	}
}

func findMatchesInAllLines(text string, re *regexp.Regexp) [][]string {
	ms := [][]string{}
	for _, s := range strings.Split(text, "\n") {
		ms = append(ms, re.FindAllStringSubmatch(s, -1)...)
	}
	return ms
}

func unwrapLastSubmatch(matches [][]string, errContext string) string {
	ss := unwrapSubmatches(matches, errContext)
	switch len(ss) {
	case 0:
		return ""
	default:
		return ss[len(ss)-1]
	}
}

func unwrapSubmatches(matches [][]string, errContext string) []string {
	ss := make([]string, 0, len(matches))
	for _, m := range matches {
		if len(m) != 2 {
			// Number of sub-matches is determined only by the regexp
			// definitions in this module.
			// Incorrect number of sub-matches is thus a programming error that
			// will cause a panic() on *every* successful match.
			panic(fmt.Sprintf("%s: match has %d submatches, want 1: %s", errContext, len(m), m[1:]))
		}
		ss = append(ss, m[1])
	}
	return ss
}

func parseSyncCount(text string, tm *testMetadata) error {
	ms := findMatchesInAllLines(text, syncCountPattern)
	sc := unwrapLastSubmatch(ms, "parseSyncCount")
	if sc == "" {
		return nil
	}
	var err error
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
	sc := unwrapLastSubmatch(ms, "parseRetries")
	if sc == "" {
		setDefaultRetries(tm)
		return nil
	}
	var err error
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
	cl, _ := stripMatchingQuotes(unwrapLastSubmatch(ms, "parseDependencies"))
	for _, s := range splitAndTrimCommaList(cl) {
		tm.Dependencies = append(tm.Dependencies, &api.AutotestTaskDependency{Label: s})
	}
	return nil
}

func splitAndTrimCommaList(cl string) []string {
	ret := []string{}
	ss := strings.Split(cl, ",")
	for _, s := range ss {
		s = strings.Trim(s, " \t")
		if s != "" {
			ret = append(ret, s)
		}
	}
	return ret
}

func parseSuites(text string, tm *testMetadata) {
	tm.Suites = extractSingleLineSuites(text)
	tm.Suites = append(tm.Suites, extractMultilineSuites(text)...)
}

func extractSingleLineSuites(text string) []string {
	ms := findMatchesInAllLines(text, attributesPattern)
	attrs, _ := stripMatchingQuotes(unwrapLastSubmatch(ms, "extractSingleLineSuites"))
	return extractSuitesFromAttributes(attrs)
}

func extractMultilineSuites(text string) []string {
	attrs := extractMultilineAttributes(text)
	return extractSuitesFromAttributes(attrs)
}

func extractSuitesFromAttributes(s string) []string {
	return findAndStripPrefixFromEach(splitAndTrimCommaList(s), "suite:")
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

func extractMultilineAttributes(text string) string {
	s := unwrapLastSubmatch(multilineAttributesPattern.FindAllStringSubmatch(text, -1), "parseMultilineSuites")
	return mergeAttributeLines(s)
}

// mergeAttributeLines returns the empty string for corrupted multi-line
// attributes (e.g. 'something with non-matching quotes").
func mergeAttributeLines(s string) string {
	ls := strings.Split(s, "\n")
	m := ""
	for _, el := range ls {
		el = strings.Trim(el, " \t")
		if el == "" {
			continue
		}
		el, ok := stripMatchingQuotes(el)
		if !ok {
			return ""
		}
		m += el
	}
	return m
}

// stripMatchingQuotes strips out matching quotes from the given string.
// bool return value indicates if the incoming string was well-formed and
// successfully unquoted.
func stripMatchingQuotes(s string) (string, bool) {
	if len(s) < 2 {
		return "", false
	}
	if hasSurroundingCharacter(s, "'") || hasSurroundingCharacter(s, "\"") {
		return s[1 : len(s)-1], true
	}
	return "", false
}

func hasSurroundingCharacter(s string, c string) bool {
	if len(s) < 2 {
		panic(fmt.Sprintf("hasSurroundingCharacter called with too-short string \"%s\"", s))
	}
	return strings.HasPrefix(s, c) && strings.HasSuffix(s, c)
}

func parseSuiteName(text string, as *api.AutotestSuite) {
	ms := findMatchesInAllLines(text, namePattern)
	as.Name, _ = stripMatchingQuotes(unwrapLastSubmatch(ms, "parseSuiteName"))
}

func parseChildDependencies(text string, as *api.AutotestSuite) {
	ms := findMatchesInAllLines(text, suiteDependenciesPattern)
	cl, _ := stripMatchingQuotes(unwrapLastSubmatch(ms, "parseChildDependencies"))
	for _, s := range splitAndTrimCommaList(cl) {
		as.ChildDependencies = append(as.ChildDependencies, &api.AutotestTaskDependency{Label: s})
	}
}

var (
	namePattern                = regexp.MustCompile(`^\s*NAME\s*=\s*(['"][\w\.-]+['"])\s*`)
	testTypePattern            = regexp.MustCompile(`^\s*TEST_TYPE\s*=\s*(['"]\w+['"])\s*`)
	syncCountPattern           = regexp.MustCompile(`^\s*SYNC_COUNT\s*=\s*(\d+)\s*`)
	retriesPattern             = regexp.MustCompile(`^\s*JOB_RETRIES\s*=\s*(\d+)\s*`)
	dependenciesPattern        = regexp.MustCompile(`^\s*DEPENDENCIES\s*=\s*(['"][\s\w\.,:-]+['"])\s*`)
	attributesPattern          = regexp.MustCompile(`^\s*ATTRIBUTES\s*=\s*[\(]?\s*(['"][\s\w\.,:-]+['"])\s*[\)]?\s*`)
	multilineAttributesPattern = regexp.MustCompile(`^\s*ATTRIBUTES\s*=\s*\(((?:\n*\s*(?:['"][\s\w\.,:-]+['"])\s*\n*)*)\)\s*`)
	suiteDependenciesPattern   = regexp.MustCompile(`^\s*args_dict\s*\[\s*['"]suite_dependencies['"]\s*\]\s*=\s*(['"][\s\w\.,:-]+['"])\s*`)
)
