// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package metrics

import (
	"strings"
	"testing"
)

func TestExtractsMetrics(t *testing.T) {
	jsonInput := strings.NewReader(
		`{"metrics_version": 1,
		  "python_version": "2.7.13",
		  "git_version": "2.18.1",
		  "execution_time": 1000,
		  "timestamp": 0,
		  "exit_code": 0,
		  "command": "gclient config",
		  "depot_tools_age": 1234,
		  "host_arch": "x86",
		  "host_os": "linux"}`)
	expectedStrings := map[string]string{
		"python_version": "2.7.13",
		"git_version":    "2.18.1",
		"command":        "gclient config",
		"host_arch":      "x86",
		"host_os":        "linux",
	}
	expectedNumbers := map[string]float64{
		"metrics_version": 1,
		"execution_time":  1000,
		"timestamp":       0,
		"exit_code":       0,
		"depot_tools_age": 1234,
	}

	m, err := extractMetrics(jsonInput)
	if err != nil {
		t.Fatalf("extractMetrics failed unexpectedly with %v\n", err)
	}
	for k, v := range expectedStrings {
		if actualV, ok := m[k].(string); !ok {
			t.Errorf("Field %v not found, or has the wrong type.", k)
		} else if actualV != v {
			t.Errorf("Unexpected value for %v: expected=%v got=%v\n", k, v, actualV)
		} else {
			delete(m, k)
		}
	}
	for k, v := range expectedNumbers {
		if actualV, ok := m[k].(float64); !ok {
			t.Errorf("Field %v not found, or has the wrong type.", k)
		} else if actualV != v {
			t.Errorf("Unexpected value for %v: expected=%v got=%v\n", k, v, actualV)
		} else {
			delete(m, k)
		}
	}
	if len(m) != 0 {
		t.Errorf("Unexpected extra fields: %v\n", m)
	}
}

func TestRejectsBadReports(t *testing.T) {
	testCases := [][2]string{
		{
			"malformed input",
			`{"metrics_version": }`,
		},
		{
			"unknown field",
			`{"unknown_field": 5.14}`,
		},
		{
			"non integer format version",
			`{"metrics_version": "foo"}`,
		},
		{
			"invalid metrics_version version",
			`{"metrics_version": -1}`,
		},
		{
			"invalid timestamp",
			`{"timestamp": -1}`,
		},
		{
			"unknown command",
			`{"command": "foo"}`,
		},
		{
			"unknown arguments",
			`{"arguments": ["foo"]}`,
		},
		{
			"invalid execution_time",
			`{"execution_time": -1}`,
		},
		{
			"invalid exit_code",
			`{"exit_code": 3.14159}`,
		},
		{
			"unknown host_os",
			`{"host_os": "foo"}`,
		},
		{
			"unknown host_arch",
			`{"host_arch": "foo"}`,
		},
		{
			"invalid depot_tools_age",
			`{"depot_tools_age": -3}`,
		},
		{
			"invalid python_version",
			`{"python_version": "3.15.15 foo"}`,
		},
		{
			"invalid git_version",
			`{"git_version": "2.18.5 ogle"}`,
		},
		{
			"unknown sub_command field",
			`{"sub_commands": [{"unknown_field": "foo"}]}`,
		},
		{
			"unknown sub_command command",
			`{"sub_commands": [{"command": "foo"}]}`,
		},
		{
			"unknown sub_command arguments",
			`{"sub_commands": [{"arguments": ["foo"]}]}`,
		},
		{
			"invalid sub_command execution_time",
			`{"sub_commands": [{"execution_time": -1}]}`,
		},
		{
			"invalid sub_command exit_code",
			`{"sub_commands": [{"exit_code": 1.337}]}`,
		},
		{
			"unknown http_requests field",
			`{"http_requests": [{"unknown_field": "foo"}]}`,
		},
		{
			"unknown http_requests host",
			`{"http_requests": [{"host": "foo"}]}`,
		},
		{
			"unknown http_requests method",
			`{"http_requests": [{"method": "LEMUR"}]}`,
		},
		{
			"unknown http_requests path",
			`{"http_requests": [{"path": "changes/unknown"}]}`,
		},
		{
			"unknown http_requests arguments",
			`{"http_requests": [{"arguments": ["foo"]}]}`,
		},
		{
			"invalid http_requests status",
			`{"http_requests": [{"status": 666}]}`,
		},
		{
			"invalid http_requests response_time",
			`{"http_requests": [{"response_time": -1.337}]}`,
		},
	}
	for _, testCase := range testCases {
		jsonInput := strings.NewReader(testCase[1])
		_, err := extractMetrics(jsonInput)
		if err == nil {
			t.Errorf("Expected extractMetrics to fail on %v because of %v.", testCase[1], testCase[0])
		}
	}
}
