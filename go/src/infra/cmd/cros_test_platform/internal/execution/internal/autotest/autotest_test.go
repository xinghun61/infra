// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest_test

import (
	"context"
	"strings"
	"sync"
	"testing"

	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"

	"infra/cmd/cros_test_platform/internal/execution/internal/autotest"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
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
		Scheduling: &test_platform.Request_Params_Scheduling{
			Pool: &test_platform.Request_Params_Scheduling_ManagedPool_{
				ManagedPool: test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ,
			},
		},
		Time: &test_platform.Request_Params_Time{
			MaximumDuration: &duration.Duration{Seconds: 60 * 60},
		},
		Decorations: &test_platform.Request_Params_Decorations{
			AutotestKeyvals: map[string]string{"k1": "v1"},
		},
	}
}

func basicConfig() *config.Config_AutotestBackend {
	return &config.Config_AutotestBackend{
		AfeHost: "foo-afe-host",
	}
}

func TestLaunch(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := NewFakeSwarming()
		// Pretend to be immediately completed, so that LaunchAndWait returns
		// immediately after launching.
		swarming.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})

		var invs []*steps.EnumerationResponse_AutotestInvocation
		invs = append(invs, invocation("test1"), invocation("test2"))

		Convey("when running a autotest execution", func() {
			run := autotest.New(invs, basicParams(), basicConfig())

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
					"--pool", "cq",
					"-w", "foo-afe-host",
					"--timeout_mins", "60",
					"--suite_args_json",
					`{"args_dict_json":"{\"job_keyvals\":{\"k1\":\"v1\"},\"name\":\"cros_test_platform\",\"test_names\":[\"test1\",\"test2\"]}"}`,
				}
				So(cmd, ShouldResemble, expected)
			})
		})
	})
}

func TestLaunchLegacy(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := NewFakeSwarming()
		// Pretend to be immediately completed, so that LaunchAndWait returns
		// immediately after launching.
		swarming.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})

		var invs []*steps.EnumerationResponse_AutotestInvocation
		invs = append(invs, invocation("test1"), invocation("test2"))

		Convey("when running a autotest execution with a legacy suite", func() {
			p := basicParams()
			p.Legacy = &test_platform.Request_Params_Legacy{
				AutotestSuite: "legacy_suite",
			}
			run := autotest.New(invs, p, basicConfig())

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
					"--suite_name", "legacy_suite",
					"--pool", "cq",
					"-w", "foo-afe-host",
					"--timeout_mins", "60",
					"--suite_args_json", "{}",
				}
				So(cmd, ShouldResemble, expected)
			})
		})
	})
}

func TestLaunchWithDisplayName(t *testing.T) {
	Convey("Given one enumerated test", t, func() {
		ctx := context.Background()
		swarming := NewFakeSwarming()
		setupFakeSwarmingToPassAllTasks(swarming)
		invs := []*steps.EnumerationResponse_AutotestInvocation{
			{
				Test:        &build_api.AutotestTest{Name: "testName"},
				DisplayName: "displayName",
				TestArgs:    "-ignored -args",
			},
		}

		Convey("when running an autotest execution", func() {
			run := autotest.New(invs, basicParams(), basicConfig())
			err := run.LaunchAndWait(ctx, swarming, nil)
			So(err, ShouldBeNil)
			Convey("then autotest invocation uses display name for the control file name.", func() {
				So(swarming.createCalls, ShouldHaveLength, 1)
				So(swarming.createCalls[0].TaskSlices, ShouldHaveLength, 1)
				cmd := strings.Join(swarming.createCalls[0].TaskSlices[0].Properties.Command, " ")
				So(cmd, ShouldContainSubstring, `\"test_names\":[\"displayName\"]`)
			})
		})
	})
}

// setupFakeSwarmingToPassAllTasks sets up fakeSwarming such that all future
// tasks are marked as completing successfully immediately.
func setupFakeSwarmingToPassAllTasks(s *fakeSwarming) {
	s.SetResult(&swarming_api.SwarmingRpcsTaskResult{State: "COMPLETED"})
	s.SetOutput(`#JSON_START#{"return_code": 0}#JSON_END#`)
}

func TestLaunchWithTestArgsReturnsError(t *testing.T) {
	Convey("Given one enumerated test", t, func() {
		ctx := context.Background()
		swarming := NewFakeSwarming()
		setupFakeSwarmingToPassAllTasks(swarming)
		invs := []*steps.EnumerationResponse_AutotestInvocation{
			{
				Test:     &build_api.AutotestTest{Name: "testName"},
				TestArgs: "-disallowed -args",
			},
		}

		Convey("running an autotest execution with test args should return error", func() {
			run := autotest.New(invs, basicParams(), basicConfig())
			err := run.LaunchAndWait(ctx, swarming, nil)
			So(err, ShouldNotBeNil)
		})
	})
}

var running = &steps.ExecuteResponse{State: &test_platform.TaskState{LifeCycle: test_platform.TaskState_LIFE_CYCLE_RUNNING}}

func TestWaitAndCollect(t *testing.T) {
	Convey("Given a launched autotest execution request", t, func() {
		ctx, cancel := context.WithCancel(context.Background())
		swarming := NewFakeSwarming()
		run := autotest.New(nil, basicParams(), basicConfig())

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

func invocation(name string) *steps.EnumerationResponse_AutotestInvocation {
	return &steps.EnumerationResponse_AutotestInvocation{
		Test: &build_api.AutotestTest{Name: name},
	}
}
