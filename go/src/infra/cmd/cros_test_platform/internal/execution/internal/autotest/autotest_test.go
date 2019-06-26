// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest_test

import (
	"context"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/cmd/cros_test_platform/internal/execution/internal/autotest"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
)

type fakeSwarming struct {
	createCalls []*swarming_api.SwarmingRpcsNewTaskRequest
}

func (f *fakeSwarming) CreateTask(ctx context.Context, req *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error) {
	f.createCalls = append(f.createCalls, req)
	return &swarming_api.SwarmingRpcsTaskRequestMetadata{TaskId: "task_1"}, nil
}

func (f *fakeSwarming) GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	return nil, errors.New("not yet implemented")
}

func (f *fakeSwarming) GetTaskURL(taskID string) string {
	return ""
}

func TestLaunch(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := &fakeSwarming{}

		var tests []*build_api.AutotestTest
		tests = append(tests, newTest("test1"), newTest("test2"))
		params := &test_platform.Request_Params{
			SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
				BuildTarget: &chromiumos.BuildTarget{Name: "foo-build-target"},
			},
			HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
				Model: "foo-model",
			},
		}

		Convey("when running a autotest execution", func() {
			run := autotest.New(tests, params)

			run.LaunchAndWait(ctx, swarming)
			Convey("then a single run_suite proxy job is created, with correct arguments.", func() {
				So(swarming.createCalls, ShouldHaveLength, 1)
				So(swarming.createCalls[0].TaskSlices, ShouldHaveLength, 1)
				cmd := swarming.createCalls[0].TaskSlices[0].Properties.Command
				expected := []string{
					"/usr/local/autotest/site_utils/run_suite.py",
					"--board", "foo-build-target",
					"--model", "foo-model",
					"--suite_name", "cros_test_platform",
					"--suite_args_json", `{"args_dict_json":{"test_names":["test1","test2"]}}`,
				}
				So(cmd, ShouldResemble, expected)
			})
		})
	})
}

func newTest(name string) *build_api.AutotestTest {
	return &build_api.AutotestTest{Name: name}
}
