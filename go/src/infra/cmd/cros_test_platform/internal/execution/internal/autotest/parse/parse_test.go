// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package parse_test

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"

	"infra/cmd/cros_test_platform/internal/execution/internal/autotest/parse"
)

func TestFailures(t *testing.T) {
	Convey("When parsing a run_suite output", t, func() {
		cases := []struct {
			description string
			output      string
			errText     string
		}{
			{
				"no json line",
				"Foo Bar",
				"no start tag in output",
			},
			{
				"end tag before start tag",
				"#JSON_END#this isn't json#JSON_START#",
				"end tag before start",
			},
			{
				"bad json",
				"#JSON_START#this isn't json#JSON_END#",
				"invalid json",
			},
			{
				"no return code",
				"#JSON_START#{}#JSON_END#",
				"return_code not supplied",
			},
			{
				"invalid return code",
				`#JSON_START#{"return_code": 42}#JSON_END#`,
				"unknown return code 42",
			},
		}
		for _, c := range cases {
			Convey(fmt.Sprintf("with %s", c.description), func() {
				result, err := parse.RunSuite(c.output)
				Convey("then the correct error is returned.", func() {
					So(result, ShouldBeNil)
					So(err.Error(), ShouldContainSubstring, c.errText)
				})

			})
		}
	})
}

func TestFullSample(t *testing.T) {
	failed := &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED, Verdict: test_platform.TaskState_VERDICT_FAILED}
	passed := &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED, Verdict: test_platform.TaskState_VERDICT_PASSED}
	Convey("When parsing a maximal run_suite output example of a failed suite", t, func() {
		result, err := parse.RunSuite(fullSample)
		So(err, ShouldBeNil)
		So(result, ShouldNotBeNil)
		Convey("then the correct results are returned.", func() {
			So(result.State, ShouldResemble, failed)
			So(result.TaskResults, ShouldHaveLength, 43)

			resultByName := map[string]*steps.ExecuteResponse_TaskResult{}
			for _, t := range result.TaskResults {
				resultByName[t.Name] = t
			}
			So(resultByName["tast.video.DecodeAccelH264ResolutionSwitch"].State, ShouldResemble, failed)
			So(resultByName["tast.example.Keyboard"].State, ShouldResemble, passed)
			So(resultByName["tast.video.SeekSwitchVP8"], ShouldResemble, &steps.ExecuteResponse_TaskResult{
				TaskUrl: "http://cautotest/afe/#tab_id=view_job&object_id=319091084",
				State:   passed,
				Name:    "tast.video.SeekSwitchVP8",
				LogUrl:  "http://cautotest/tko/retrieve_logs.cgi?job=/results/319091084-chromeos-test/",
			})
		})

	})
}
