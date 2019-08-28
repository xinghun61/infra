// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dynamicsuite_test

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/libs/skylab/autotest/dynamicsuite"
)

func TestRequest(t *testing.T) {
	Convey("Given a set of arguments", t, func() {
		args := dynamicsuite.Args{
			Board: "board",
			Build: "build",
			Model: "model",
			Pool:  "pool",
			ReimageAndRunArgs: map[string]interface{}{
				"arg_1": 1,
				"arg_2": []string{"v1", "v2"},
			},
		}
		Convey("a new request has correct properties", func() {
			req, err := dynamicsuite.NewRequest(args)
			So(err, ShouldBeNil)
			So(req, ShouldNotBeNil)
			So(req.TaskSlices, ShouldHaveLength, 1)
			expected := []string{
				"/usr/local/autotest/site_utils/run_suite.py",
				"--json_dump_postfix",
				"--build", "build",
				"--board", "board",
				"--model", "model",
				"--suite_name", "cros_test_platform",
				"--pool", "pool",
				"--suite_args_json", `{"args_dict_json":"{\"arg_1\":1,\"arg_2\":[\"v1\",\"v2\"]}"}`,
			}
			So(req.TaskSlices[0].Properties.Command, ShouldResemble, expected)
		})
	})
}

func TestLegacyRequest(t *testing.T) {
	Convey("Given a set of arguments with a legacy suite", t, func() {
		args := dynamicsuite.Args{
			Board: "board",
			Build: "build",
			Model: "model",
			Pool:  "pool",
			ReimageAndRunArgs: map[string]interface{}{
				"arg_1": 1,
				"arg_2": []string{"v1", "v2"},
			},
			LegacySuite: "legacy_suite",
		}
		Convey("a new request has correct properties", func() {
			req, err := dynamicsuite.NewRequest(args)
			So(err, ShouldBeNil)
			So(req, ShouldNotBeNil)
			So(req.TaskSlices, ShouldHaveLength, 1)
			expected := []string{
				"/usr/local/autotest/site_utils/run_suite.py",
				"--json_dump_postfix",
				"--build", "build",
				"--board", "board",
				"--model", "model",
				"--suite_name", "legacy_suite",
				"--pool", "pool",
				"--suite_args_json", "{}",
			}
			So(req.TaskSlices[0].Properties.Command, ShouldResemble, expected)
		})
	})
}
