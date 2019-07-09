// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest_test

import (
	"context"
	"sync"
	"testing"

	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"

	"infra/cmd/cros_test_platform/internal/execution/internal/autotest"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

type fakeSwarming struct {
	createCalls []*swarming_api.SwarmingRpcsNewTaskRequest

	output string
	result *swarming_api.SwarmingRpcsTaskResult
}

func NewFakeSwarming() *fakeSwarming {
	return &fakeSwarming{
		result: &swarming_api.SwarmingRpcsTaskResult{
			State: "RUNNING",
		},
	}
}

func (f *fakeSwarming) CreateTask(ctx context.Context, req *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error) {
	f.createCalls = append(f.createCalls, req)
	return &swarming_api.SwarmingRpcsTaskRequestMetadata{TaskId: "task_1"}, nil
}

func (f *fakeSwarming) GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	return []*swarming_api.SwarmingRpcsTaskResult{f.result}, nil
}

func (f *fakeSwarming) GetTaskURL(taskID string) string {
	return ""
}

func (f *fakeSwarming) GetTaskOutputs(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskOutput, error) {
	return []*swarming_api.SwarmingRpcsTaskOutput{{Output: f.output}}, nil
}

func (f *fakeSwarming) SetOutput(output string) {
	f.output = output
}

func (f *fakeSwarming) SetResult(result *swarming_api.SwarmingRpcsTaskResult) {
	f.result = result
}

func basicParams() *test_platform.Request_Params {
	return &test_platform.Request_Params{
		SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
			BuildTarget: &chromiumos.BuildTarget{Name: "foo-build-target"},
		},
		HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
			Model: "foo-model",
		},
		SoftwareDependencies: []*test_platform.Request_Params_SoftwareDependency{
			{
				Dep: &test_platform.Request_Params_SoftwareDependency_ChromeosBuild{ChromeosBuild: "foo-build"},
			},
		},
		Time: &test_platform.Request_Params_Time{
			MaximumDuration: &duration.Duration{Seconds: 60 * 60},
		},
	}
}

func TestLaunch(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := NewFakeSwarming()
		// Pretend to be immediately completed, so that LaunchAndWait returns
		// immediately after launching.
		swarming.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})

		var tests []*build_api.AutotestTest
		tests = append(tests, newTest("test1"), newTest("test2"))

		Convey("when running a autotest execution", func() {
			run := autotest.New(tests, basicParams())

			run.LaunchAndWait(ctx, swarming, nil)
			Convey("then a single run_suite proxy job is created, with correct arguments.", func() {
				So(swarming.createCalls, ShouldHaveLength, 1)
				So(swarming.createCalls[0].TaskSlices, ShouldHaveLength, 1)
				cmd := swarming.createCalls[0].TaskSlices[0].Properties.Command
				expected := []string{
					"/usr/local/autotest/site_utils/run_suite.py",
					"--json_dump_postfix",
					"--build", "foo-build",
					"--board", "foo-build-target",
					"--model", "foo-model",
					"--suite_name", "cros_test_platform",
					"--timeout_mins", "60",
					"--suite_args_json", `{"args_dict_json":"{\"name\":\"cros_test_platform\",\"test_names\":[\"test1\",\"test2\"]}"}`,
				}
				So(cmd, ShouldResemble, expected)
			})
		})
	})
}

var running = &steps.ExecuteResponse{State: &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_RUNNING}}

func TestWaitAndCollect(t *testing.T) {
	Convey("Given a launched autotest execution request", t, func() {
		ctx, cancel := context.WithCancel(context.Background())
		swarming := NewFakeSwarming()
		run := autotest.New([]*build_api.AutotestTest{}, basicParams())

		wg := sync.WaitGroup{}
		wg.Add(1)
		var err error
		go func() {
			err = run.LaunchAndWait(ctx, swarming, nil)
			wg.Done()
		}()

		Convey("when the context is cancelled prior to completion, then an error is returned from launch and response is RUNNING.", func() {
			cancel()
			wg.Wait()
			So(err, ShouldNotBeNil)
			So(run.Response(swarming), ShouldResemble, running)
		})

		Convey("when the task completes, but no good json is available, then an error is returned and the response is completed with unspecified verdict.", func() {
			swarming.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})
			wg.Wait()
			So(err, ShouldNotBeNil)
			resp := run.Response(swarming)
			So(resp.State.LifeCycle, ShouldEqual, test_platform.TaskState_LIFE_CYCLE_COMPLETED)
			So(resp.State.Verdict, ShouldEqual, test_platform.TaskState_VERDICT_UNSPECIFIED)
		})

		Convey("when the task completes with valid json, then no error is returned and response is correct", func() {
			swarming.SetOutput(`#JSON_START#{"return_code": 0}#JSON_END#`)
			swarming.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})
			wg.Wait()
			So(err, ShouldBeNil)
			resp := run.Response(swarming)
			So(resp.State.LifeCycle, ShouldEqual, test_platform.TaskState_LIFE_CYCLE_COMPLETED)
			So(resp.State.Verdict, ShouldEqual, test_platform.TaskState_VERDICT_PASSED)
		})
	})
}

func newTest(name string) *build_api.AutotestTest {
	return &build_api.AutotestTest{Name: name}
}
