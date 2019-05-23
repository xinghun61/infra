// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package metrics

import (
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"infra/appengine/depot_tools_metrics/schema"
)

func TestExtractsMetrics(t *testing.T) {
	jsonInput := `
		{"metrics_version": 1,
		 "timestamp": 5678,
		 "command": "gclient config",
		 "arguments": ["verbose"],
		 "execution_time": 1000,
		 "exit_code": 0,
		 "sub_commands": [{
			"command": "git push",
			"exit_code": 1,
			"execution_time": 123,
			"arguments": ["cc", "notify=ALL", "label"]}],
		 "http_requests": [{
			"host": "chromium-review.googlesource.com",
			"method": "POST",
			"path": "changes/abandon",
			"arguments": ["ALL_REVISIONS", "LABELS"],
			"status": 403,
			"response_time": 456}],
		 "project_urls": [
			"https://chromium.googlesource.com/chromium/src",
			"https://chromium.googlesource.com/external/gyp"],
		 "depot_tools_age": 1234,
		 "host_arch": "x86",
		 "host_os": "linux",
		 "python_version": "2.7.13",
		 "git_version": "2.18.1"}`

	var metrics schema.Metrics
	err := jsonpb.UnmarshalString(jsonInput, &metrics)
	if err != nil {
		t.Fatalf("failed unexpectedly with %v\n", err)
	}

	err = checkConstraints(metrics)
	if err != nil {
		t.Fatalf("failed unexpectedly with %v\n", err)
	}
}

func TestDealsWithUnsetFields(t *testing.T) {
	jsonInput := `
		{"metrics_version": 1,
		 "timestamp": 1234,
		 "http_requests": [{
			"arguments": ["ALL_REVISIONS"],
			"status": 500
		 }],
		 "sub_commands": [{"exit_code": 0}],
		 "host_arch": "x86"}`

	var metrics schema.Metrics
	err := jsonpb.UnmarshalString(jsonInput, &metrics)
	if err != nil {
		t.Fatalf("failed unexpectedly with %v\n", err)
	}

	err = checkConstraints(metrics)
	if err != nil {
		t.Fatalf("failed unexpectedly with %v\n", err)
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
		var metrics schema.Metrics
		err := jsonpb.UnmarshalString(testCase[0], &metrics)
		if err == nil {
			err = checkConstraints(metrics)
			if err == nil {
				t.Errorf("Expected constraints for %v to fail because of %v. metrics:\n%v",
					testCase[1], testCase[0], metrics)
			}
		}
	}
}
