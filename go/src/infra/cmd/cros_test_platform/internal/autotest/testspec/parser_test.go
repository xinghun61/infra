// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"testing"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/luci/common/data/stringset"
)

func TestParseTestControlName(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want string
	}{
		{"ignore comment", `# NAME = 'platform'`, ""},
		{"single quoted name", `NAME = 'platform'`, "platform"},
		{"double quoted name", `NAME = "platform"`, "platform"},
		{"leading space", `  NAME = "platform"`, "platform"},
		{"leading tabs", `		NAME = "platform"`, "platform"},
		{"special character dot", `NAME = "platform_23Hours.almost-daily"`, "platform_23Hours.almost-daily"},
		{
			Tag: "multiline with context",
			Text: `
				AUTHOR = "somebody"
				NAME = "platform_SuspendResumeTiming"
				PURPOSE = "Servo based suspend-resume timing check test"
				CRITERIA = "This test will fail if time to suspend or resume is too long."
				TIME = "LONG"
				TEST_CATEGORY = "Functional"
				TEST_CLASS = "platform"
				TEST_TYPE = "server"
			`,
			Want: "platform_SuspendResumeTiming",
		},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			tm, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if c.Want != tm.Name {
				t.Errorf("Name differs for %s, want: %s, got %s", c.Text, c.Want, tm.Name)
			}
		})
	}
}

func TestParseTestControlExecutionEnvironment(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want api.AutotestTest_ExecutionEnvironment
	}{
		{"default value", ``, api.AutotestTest_EXECUTION_ENVIRONMENT_UNSPECIFIED},
		{"malformed value", `TEST_TYPE = "notclient"`, api.AutotestTest_EXECUTION_ENVIRONMENT_UNSPECIFIED},
		{"client test", `TEST_TYPE = "client"`, api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT},
		{"server test", `TEST_TYPE = 'server'`, api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER},
		{"server test mixed case", `TEST_TYPE = 'SeRvEr'`, api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			as, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if as.ExecutionEnvironment != c.Want {
				t.Errorf("ExecutionEnvironment differs for |%s|: got %s, want %s",
					c.Text, as.ExecutionEnvironment.String(), c.Want.String())
			}
		})
	}
}

func TestParseTestControlSyncCount(t *testing.T) {
	var cases = []struct {
		Tag                   string
		Text                  string
		WantNeedsMultipleDuts bool
		WantDutCount          int32
	}{
		{"default value", ``, false, 0},
		{"explicit zero", `SYNC_COUNT = 0`, false, 0},
		{"multi dut", `SYNC_COUNT = 3`, true, 3},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			tm, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if c.WantNeedsMultipleDuts != tm.NeedsMultipleDuts {
				t.Errorf("NeedsMultipleDuts differs for |%s|, want: %t, got %t", c.Text, c.WantNeedsMultipleDuts, tm.NeedsMultipleDuts)
			}
			if c.WantDutCount != tm.DutCount {
				t.Errorf("NeedsMultipleDuts differs for |%s|, want: %d, got %d", c.Text, c.WantDutCount, tm.DutCount)
			}
		})
	}
}

func TestParseTestControlRetries(t *testing.T) {
	var cases = []struct {
		Tag              string
		Text             string
		WantAllowRetries bool
		WantMaxRetries   int32
	}{
		{"default value", ``, true, 1},
		{"multiple retries", `JOB_RETRIES = 3`, true, 3},
		{"no retries", `JOB_RETRIES = 0`, false, 0},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			tm, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if c.WantAllowRetries != tm.AllowRetries {
				t.Errorf("AllowRetries differs for |%s|, want: %t, got %t", c.Text, c.WantAllowRetries, tm.AllowRetries)
			}
			if c.WantMaxRetries != tm.MaxRetries {
				t.Errorf("MaxRetries differs for |%s|, want: %d, got %d", c.Text, c.WantMaxRetries, tm.MaxRetries)
			}
		})
	}
}

func TestParseTestControlDependencies(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want stringset.Set
	}{
		{"default value", ``, stringset.NewFromSlice()},
		{"one value", `DEPENDENCIES = 'dep'`, stringset.NewFromSlice("dep")},
		{"one valuewith colon", `DEPENDENCIES = 'model:mario'`, stringset.NewFromSlice("model:mario")},
		{"two values with space", `DEPENDENCIES = "dep1, dep2"`, stringset.NewFromSlice("dep1", "dep2")},
		{"two values without space", `DEPENDENCIES = "dep1,dep2"`, stringset.NewFromSlice("dep1", "dep2")},
		{"two values with trailing comma", `DEPENDENCIES = "dep1,dep2,"`, stringset.NewFromSlice("dep1", "dep2")},
		// Control file fields are just python global variable assignments.
		// If the same global variable is assigned multiple times, lexically
		// last assignment wins.
		{
			Tag: "multiple assignments",
			Text: `
				DEPENDENCIES = "dep1"
				DEPENDENCIES = "dep2"`,
			Want: stringset.NewFromSlice("dep2"),
		},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			tm, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if diff := pretty.Compare(c.Want, autotestLabelSet(tm.Dependencies)); diff != "" {
				t.Errorf("Dependencies differ for |%s|, -want, +got, %s", c.Text, diff)
			}
		})
	}
}

func autotestLabelSet(deps []*api.AutotestTaskDependency) stringset.Set {
	s := stringset.New(len(deps))
	for _, d := range deps {
		s.Add(d.Label)
	}
	return s
}

func TestParseTestControlSuites(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want stringset.Set
	}{
		{"default value", ``, stringset.NewFromSlice()},
		{"unrelated dependency", `ATTRIBUTES = 'dep'`, stringset.NewFromSlice()},
		{"one suite", `ATTRIBUTES = 'suite:network_nightly'`, stringset.NewFromSlice("network_nightly")},
		{"two suites", `ATTRIBUTES = "suite:bvt, suite:bvt-inline"`, stringset.NewFromSlice("bvt", "bvt-inline")},
		{"one suite in context", `ATTRIBUTES = "suite:cts,another_attribute"`, stringset.NewFromSlice("cts")},
		{"one suite with tabs", `ATTRIBUTES = "	suite:cts	"`, stringset.NewFromSlice("cts")},
		{"one suite with mistmatched quotes", `ATTRIBUTES = "suite:cts'`, stringset.NewFromSlice()},
		{"suite in parens", `ATTRIBUTES = ('suite:network_nightly')`, stringset.NewFromSlice("network_nightly")},
		{"suite in parens and space", `ATTRIBUTES = ( 'suite:network_nightly' )`, stringset.NewFromSlice("network_nightly")},
		{
			"suite in parens and newline with spaces",
			`ATTRIBUTES = ('suite:network_nightly,'
                           "suite:cq")`,
			stringset.NewFromSlice("network_nightly", "cq"),
		},
		{
			"suite in parens and newline with tabs",
			`ATTRIBUTES = (
				'suite:network_nightly,'
				"suite:cq"
			)`,
			stringset.NewFromSlice("network_nightly", "cq"),
		},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			tm, err := parseTestControl(c.Text)
			if err != nil {
				t.Fatalf("parseTestControl: %s", err)
			}
			if diff := pretty.Compare(c.Want, stringset.NewFromSlice(tm.Suites...)); diff != "" {
				t.Errorf("Suites differ for |%s|, -want, +got, %s", c.Text, diff)
			}
		})
	}
}

func TestParseSuiteControlName(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want string
	}{
		{"default value", ``, ""},
		{"mismatched quotes", `NAME = 'some_suite"`, ""},
		{"incorrect key", `SUITE = "some_suite"`, ""},
		{"happy case", `NAME = "some_suite"`, "some_suite"},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			as, err := parseSuiteControl(c.Text)
			if err != nil {
				t.Fatalf("parseSuiteControl: %s", err)
			}
			if c.Want != as.Name {
				t.Errorf("Suite name differs for |%s|, want %s, +got %s", c.Text, c.Want, as.Name)
			}
		})
	}
}

func TestParseSuiteControlChildDependencies(t *testing.T) {
	var cases = []struct {
		Tag  string
		Text string
		Want stringset.Set
	}{
		{"default value", ``, stringset.NewFromSlice()},
		{"incorrect format", `SUITE_DEPENDENCIES = 'model:mario'`, stringset.NewFromSlice()},
		{"correct format", `args_dict['suite_dependencies'] = 'carrier:verizon,modem_repair'`, stringset.NewFromSlice("carrier:verizon", "modem_repair")},
	}

	for _, c := range cases {
		t.Run(c.Tag, func(t *testing.T) {
			as, err := parseSuiteControl(c.Text)
			if err != nil {
				t.Fatalf("parseSuiteControl: %s", err)
			}
			if diff := pretty.Compare(c.Want, autotestLabelSet(as.ChildDependencies)); diff != "" {
				t.Errorf("ChildDependencies differ for |%s|, -want, +got, %s", c.Text, diff)
			}
		})
	}
}
