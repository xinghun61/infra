// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package parse parses the output of run_suite, to determine test and suite
// results.
package parse

import (
	"encoding/json"
	"fmt"
	"strings"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/errors"
)

const (
	startTag = "#JSON_START#"
	endTag   = "#JSON_END#"
)

type returnCode int

// run_suite.py return code meanings, per run_suite_common.py:
//
// RETURN_CODES = enum.Enum(
//	'OK',
//	'ERROR',
//	'WARNING',
//	'INFRA_FAILURE',
//	'SUITE_TIMEOUT',
//	'BOARD_NOT_AVAILABLE',
//	'INVALID_OPTIONS',
// )
const (
	codeOK returnCode = iota
	codeError
	codeWarning
	codeInfraFailure
	codeSuiteTimeout
	codeBoardNotAvailable
	codeInvalidOptions
)

var passed = test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED, Verdict: test_platform.TaskState_VERDICT_PASSED}
var failed = test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED, Verdict: test_platform.TaskState_VERDICT_FAILED}

var returnCodeStatuses = map[returnCode]test_platform.TaskState{
	codeOK: passed,
	// codeError means the suite failed.
	codeError: failed,
	// codeWarning means the suite passed, with warnings.
	codeWarning: passed,
	// TODO(akeshet): Currently treating all of the remaining codes as "failed".
	// Some of them may actually map better to aborted or no-verdict.
	codeInfraFailure:      failed,
	codeSuiteTimeout:      failed,
	codeBoardNotAvailable: failed,
	codeInvalidOptions:    failed,
}

// Possible test statuses, per the tko.tko_status table.
var testStatuses = map[string]test_platform.TaskState{
	"NOSTATUS": {},
	// TODO(akeshet): I'm not clear on the meaning of "ERROR" status; treating
	// is as equivalent to "FAIL".
	"ERROR": failed,
	"ABORT": {LifeCycle: test_platform.TaskState_LIFE_CYCLE_ABORTED},
	"FAIL":  failed,
	"WARN":  passed,
	"GOOD":  passed,
	// TODO(akeshet): I'm not clear on the meaning of "ALERT" status; treating
	// it as equivalent to "FAIL".
	"ALERT":   failed,
	"TEST_NA": {LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED, Verdict: test_platform.TaskState_VERDICT_NO_VERDICT},
	"RUNNING": {LifeCycle: test_platform.TaskState_LIFE_CYCLE_RUNNING},
}

// report describes the structure of json data emitted by run_suite.py
type report struct {
	// AutotestInstance is the hostname of the autotest instance where the
	// task ran. In practice this is always either "cautotest" or
	// "cautotest-staging"
	AutotestInstance string `json:"autotest_instance"`
	// Use a pointer type to distinguish 0 from unsupplied, as this is a
	// required field.
	ReturnCode    *returnCode `json:"return_code"`
	ReturnMessage string      `json:"return_message"`
	SuiteJobID    int         `json:"suite_job_id"`
	Tests         map[string]struct {
		Status     string `json:"status"`
		Reason     string `json:"reason"`
		LinkToLogs string `json:"link_to_logs"`
		JobID      int    `json:"job_id"`
	} `json:"tests"`
}

// RunSuite parses the output of run_suite.py.
func RunSuite(output string) (*steps.ExecuteResponse, error) {
	json, err := findJSON(output)
	if err != nil {
		return nil, err
	}

	rep, err := parseJSON(json)
	if err != nil {
		return nil, err
	}

	return parseReport(rep)
}

func findJSON(output string) (string, error) {
	start := strings.Index(output, startTag)
	if start == -1 {
		return "", errors.Reason("no start tag in output").Err()
	}

	end := strings.Index(output, endTag)
	if end == -1 {
		return "", errors.Reason("no end tag in output").Err()
	}

	if end < start {
		return "", errors.Reason("end tag before start tag in output").Err()
	}

	return output[start+len(startTag) : end], nil
}

func parseJSON(line string) (*report, error) {
	bytes := []byte(line)
	if !json.Valid(bytes) {
		return nil, errors.Reason("invalid json: %s", line).Err()
	}
	resp := &report{}
	err := json.Unmarshal(bytes, resp)
	if err != nil {
		return nil, errors.Annotate(err, "parse json").Err()
	}
	return resp, nil
}

func parseReport(rep *report) (*steps.ExecuteResponse, error) {
	resp := &steps.ExecuteResponse{}

	state, err := unpackReturnCode(rep.ReturnCode)
	if err != nil {
		return nil, errors.Annotate(err, "parse report").Err()
	}
	resp.State = state

	for testName, result := range rep.Tests {
		state, err := unpackStatus(result.Status)
		if err != nil {
			return nil, errors.Annotate(err, "parse report for test named %s", testName).Err()
		}

		taskResult := &steps.ExecuteResponse_TaskResult{
			Name:    testName,
			LogUrl:  result.LinkToLogs,
			TaskUrl: taskURL(rep.AutotestInstance, result.JobID),
			State:   state,
		}
		resp.TaskResults = append(resp.TaskResults, taskResult)
	}
	return resp, nil
}

func unpackStatus(status string) (*test_platform.TaskState, error) {
	state, ok := testStatuses[status]
	if !ok {
		return nil, errors.Reason("unknown status %s", status).Err()
	}
	return &state, nil
}

func unpackReturnCode(code *returnCode) (*test_platform.TaskState, error) {
	if code == nil {
		return nil, errors.Reason("return_code not supplied").Err()
	}

	state, ok := returnCodeStatuses[*code]
	if !ok {
		return nil, errors.Reason("unknown return code %d", *code).Err()
	}
	return &state, nil
}

func taskURL(autotestInstance string, jobID int) string {
	if jobID == 0 {
		return ""
	}
	return fmt.Sprintf("http://%s/afe/#tab_id=view_job&object_id=%d", autotestInstance, jobID)
}
