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
		Text string
		Want string
	}{
		{`# NAME = 'platform'`, ""},
		{`NAME = 'platform'`, "platform"},
		{`NAME = "platform"`, "platform"},
		{`  NAME = "platform"`, "platform"},
		{`		NAME = "platform"`, "platform"},
		{`NAME = "platform_23Hours.almost-daily"`, "platform_23Hours.almost-daily"},
		{
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
		tm, err := parseTestControl(c.Text)
		if err != nil {
			t.Fatalf("parseTestControl: %s", err)
		}
		if c.Want != tm.Name {
			t.Errorf("Name differs for %s, want: %s, got %s", c.Text, c.Want, tm.Name)
		}
	}
}

func TestParseTestControlSyncCount(t *testing.T) {
	var cases = []struct {
		Text                  string
		WantNeedsMultipleDuts bool
		WantDutCount          int32
	}{
		{``, false, 0},
		{`SYNC_COUNT = 0`, false, 0},
		{`SYNC_COUNT = 3`, true, 3},
	}

	for _, c := range cases {
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
	}
}

func TestParseTestControlRetries(t *testing.T) {
	var cases = []struct {
		Text             string
		WantAllowRetries bool
		WantMaxRetries   int32
	}{
		{`JOB_RETRIES = 3`, true, 3},
		{`JOB_RETRIES = 0`, false, 0},
		// JOB_RETRIES must be explicitly set to 0 to disallow retries. Default is 1 retry.
		{``, true, 1},
	}

	for _, c := range cases {
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
	}
}

func TestParseTestControlDependencies(t *testing.T) {
	var cases = []struct {
		Text string
		Want stringset.Set
	}{
		{``, stringset.NewFromSlice()},
		{`DEPENDENCIES = 'dep'`, stringset.NewFromSlice("dep")},
		{`DEPENDENCIES = 'model:mario'`, stringset.NewFromSlice("model:mario")},
		{`DEPENDENCIES = "dep1, dep2"`, stringset.NewFromSlice("dep1", "dep2")},
		{`DEPENDENCIES = "dep1,dep2"`, stringset.NewFromSlice("dep1", "dep2")},
		{`DEPENDENCIES = "dep1,dep2,"`, stringset.NewFromSlice("dep1", "dep2")},
	}

	for _, c := range cases {
		tm, err := parseTestControl(c.Text)
		if err != nil {
			t.Fatalf("parseTestControl: %s", err)
		}
		if diff := pretty.Compare(c.Want, autotestLabelSet(tm.Dependencies)); diff != "" {
			t.Errorf("Dependencies differ for |%s|, -want, +got, %s", c.Text, diff)
		}
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
		Text string
		Want stringset.Set
	}{
		{``, stringset.NewFromSlice()},
		{`ATTRIBUTES = 'dep'`, stringset.NewFromSlice()},
		{`ATTRIBUTES = 'suite:network_nightly'`, stringset.NewFromSlice("network_nightly")},
		{`ATTRIBUTES = "suite:bvt, suite:bvt-inline"`, stringset.NewFromSlice("bvt", "bvt-inline")},
		{`ATTRIBUTES = "suite:cts,another_attribute"`, stringset.NewFromSlice("cts")},
	}

	for _, c := range cases {
		tm, err := parseTestControl(c.Text)
		if err != nil {
			t.Fatalf("parseTestControl: %s", err)
		}
		if diff := pretty.Compare(c.Want, stringset.NewFromSlice(tm.Suites...)); diff != "" {
			t.Errorf("Suites differ for |%s|, -want, +got, %s", c.Text, diff)
		}
	}
}

func TestParseSuiteControlChildDependencies(t *testing.T) {
	var cases = []struct {
		Text string
		Want stringset.Set
	}{
		{``, stringset.NewFromSlice()},
		{`SUITE_DEPENDENCIES = 'model:mario'`, stringset.NewFromSlice()},
		{`args_dict['suite_dependencies'] = 'carrier:verizon,modem_repair'`, stringset.NewFromSlice("carrier:verizon", "modem_repair")},
	}

	for _, c := range cases {
		as, err := parseSuiteControl(c.Text)
		if err != nil {
			t.Fatalf("parseSuiteControl: %s", err)
		}
		if diff := pretty.Compare(c.Want, autotestLabelSet(as.ChildDependencies)); diff != "" {
			t.Errorf("ChildDependencies differ for |%s|, -want, +got, %s", c.Text, diff)
		}
	}
}
