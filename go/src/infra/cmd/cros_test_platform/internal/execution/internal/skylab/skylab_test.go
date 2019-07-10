// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab_test

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/execution/internal/skylab"
	"infra/cmd/cros_test_platform/internal/execution/isolate"
)

// fakeSwarming implements skylab.Swarming
type fakeSwarming struct {
	nextID      int
	nextState   jsonrpc.TaskState
	nextError   error
	callback    func()
	server      string
	createCalls []*swarming_api.SwarmingRpcsNewTaskRequest
	getCalls    [][]string
	hasRef      bool
}

func (f *fakeSwarming) CreateTask(ctx context.Context, req *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error) {
	defer f.callback()
	f.nextID++
	f.createCalls = append(f.createCalls, req)
	if f.nextError != nil {
		return nil, f.nextError
	}
	resp := &swarming_api.SwarmingRpcsTaskRequestMetadata{TaskId: fmt.Sprintf("task%d", f.nextID)}
	return resp, nil
}

func (f *fakeSwarming) GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	defer f.callback()
	f.getCalls = append(f.getCalls, IDs)
	if f.nextError != nil {
		return nil, f.nextError
	}

	var ref *swarming_api.SwarmingRpcsFilesRef
	if f.hasRef {
		ref = &swarming_api.SwarmingRpcsFilesRef{}
	}

	results := make([]*swarming_api.SwarmingRpcsTaskResult, len(IDs))
	for i, taskID := range IDs {
		results[i] = &swarming_api.SwarmingRpcsTaskResult{
			TaskId:     taskID,
			State:      jsonrpc.TaskState_name[int32(f.nextState)],
			OutputsRef: ref,
		}
	}
	return results, nil
}

func (f *fakeSwarming) GetTaskURL(taskID string) string {
	// Note: this is not the true swarming task URL schema.
	return f.server + "/task=" + taskID
}

func (f *fakeSwarming) GetTaskOutputs(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskOutput, error) {
	return nil, nil
}

// setTaskState causes this fake to start returning the given state of all future
func (f *fakeSwarming) setTaskState(state jsonrpc.TaskState) {
	f.nextState = state
}

func (f *fakeSwarming) setHasOutputRef(has bool) {
	f.hasRef = has
}

// setError causes this fake to start returning the given error on all
// future API calls.
func (f *fakeSwarming) setError(err error) {
	f.nextError = err
}

// setCallback causes this fake to call the given callback function, immediately
// prior to the return of every future API call.
func (f *fakeSwarming) setCallback(fn func()) {
	f.callback = fn
}

func newFakeSwarming(server string) *fakeSwarming {
	return &fakeSwarming{
		nextState: jsonrpc.TaskState_COMPLETED,
		callback:  func() {},
		server:    server,
		hasRef:    true,
	}
}

type fakeGetter struct {
	content []byte
}

func (g *fakeGetter) GetFile(_ context.Context, _ isolated.HexDigest, _ string) ([]byte, error) {
	return g.content, nil
}

func (g *fakeGetter) SetResult(res *skylab_test_runner.Result) {
	m := &jsonpb.Marshaler{}
	s, _ := m.MarshalToString(res)
	g.content = []byte(s)
}

func (g *fakeGetter) SetAutotestResult(res *skylab_test_runner.Result_Autotest) {
	r := &skylab_test_runner.Result{}
	r.Harness = &skylab_test_runner.Result_AutotestResult{AutotestResult: res}
	g.SetResult(r)
}

func newFakeGetter() *fakeGetter {
	f := &fakeGetter{}
	f.SetAutotestResult(&skylab_test_runner.Result_Autotest{
		TestCases: []*skylab_test_runner.Result_Autotest_TestCase{
			{Name: "foo", Verdict: skylab_test_runner.Result_Autotest_TestCase_VERDICT_PASS},
		},
	})
	return f
}

func fakeGetterFactory(getter isolate.Getter) isolate.GetterFactory {
	return func(_ context.Context, _ string) (isolate.Getter, error) {
		return getter, nil
	}
}

func newTest(name string, client bool, deps ...*build_api.AutotestTaskDependency) *build_api.AutotestTest {
	ee := build_api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER
	if client {
		ee = build_api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT
	}
	return &build_api.AutotestTest{Name: name, ExecutionEnvironment: ee, Dependencies: deps}
}

func basicParams() *test_platform.Request_Params {
	return &test_platform.Request_Params{
		SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
			BuildTarget: &chromiumos.BuildTarget{Name: "foo-board"},
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
			MaximumDuration: &duration.Duration{Seconds: 60},
		},
	}
}

func basicConfig() *config.Config_SkylabWorker {
	return &config.Config_SkylabWorker{
		LuciProject: "foo-luci-project",
		LogDogHost:  "foo-logdog-host",
	}
}

func TestLaunchAndWaitTest(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := newFakeSwarming("")
		getter := newFakeGetter()
		gf := fakeGetterFactory(getter)

		var tests []*build_api.AutotestTest
		tests = append(tests, newTest("", false), newTest("", true))

		Convey("when running a skylab execution", func() {
			run := skylab.NewTaskSet(tests, basicParams(), basicConfig())

			err := run.LaunchAndWait(ctx, swarming, gf)
			So(err, ShouldBeNil)

			resp := run.Response(swarming)
			So(resp, ShouldNotBeNil)

			Convey("then results for all tests are reflected.", func() {
				So(resp.TaskResults, ShouldHaveLength, 2)
				for _, tr := range resp.TaskResults {
					So(tr.State.LifeCycle, ShouldEqual, test_platform.TaskState_LIFE_CYCLE_COMPLETED)
				}
			})
			Convey("then the expected number of external swarming calls are made.", func() {
				So(swarming.getCalls, ShouldHaveLength, 2)
				So(swarming.createCalls, ShouldHaveLength, 2)
			})
		})
	})
}

// Note: the purpose of this test is the test the behavior when a parsed
// autotest result is not available from a task, because the task didn't run
// far enough to output one.
//
// For detailed tests on the handling of autotest test results, see result_test.go.
func TestTaskStates(t *testing.T) {
	Convey("Given a single test", t, func() {
		ctx := context.Background()

		var tests []*build_api.AutotestTest
		tests = append(tests, newTest("", false))

		cases := []struct {
			description     string
			swarmingState   jsonrpc.TaskState
			hasRef          bool
			expectTaskState *test_platform.TaskState
		}{
			{
				description:   "with expired state",
				swarmingState: jsonrpc.TaskState_EXPIRED,
				hasRef:        false,
				expectTaskState: &test_platform.TaskState{
					LifeCycle: test_platform.TaskState_LIFE_CYCLE_CANCELLED,
					Verdict:   test_platform.TaskState_VERDICT_FAILED,
				},
			},
			{
				description:   "with killed state",
				swarmingState: jsonrpc.TaskState_KILLED,
				hasRef:        false,
				expectTaskState: &test_platform.TaskState{
					LifeCycle: test_platform.TaskState_LIFE_CYCLE_ABORTED,
					Verdict:   test_platform.TaskState_VERDICT_FAILED,
				},
			},
			{
				description:   "with completed state",
				swarmingState: jsonrpc.TaskState_COMPLETED,
				hasRef:        true,
				expectTaskState: &test_platform.TaskState{
					LifeCycle: test_platform.TaskState_LIFE_CYCLE_COMPLETED,
					Verdict:   test_platform.TaskState_VERDICT_NO_VERDICT,
				},
			},
		}
		for _, c := range cases {
			Convey(c.description, func() {
				swarming := newFakeSwarming("")
				swarming.setTaskState(c.swarmingState)
				swarming.setHasOutputRef(c.hasRef)
				getter := newFakeGetter()
				getter.SetAutotestResult(&skylab_test_runner.Result_Autotest{})
				gf := fakeGetterFactory(getter)

				run := skylab.NewTaskSet(tests, basicParams(), basicConfig())
				err := run.LaunchAndWait(ctx, swarming, gf)
				So(err, ShouldBeNil)

				Convey("then the task state is correct.", func() {
					resp := run.Response(swarming)
					So(resp.TaskResults, ShouldHaveLength, 1)
					So(resp.TaskResults[0].State, ShouldResemble, c.expectTaskState)
				})
			})
		}
	})
}

func TestServiceError(t *testing.T) {
	Convey("Given a single enumerated test", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming("")
		getter := newFakeGetter()
		gf := fakeGetterFactory(getter)

		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, basicParams(), basicConfig())

		Convey("when the swarming service immediately returns errors, that error is surfaced as a launch error.", func() {
			swarming.setError(fmt.Errorf("foo error"))
			err := run.LaunchAndWait(ctx, swarming, gf)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "launch test")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})

		Convey("when the swarming service starts returning errors after the initial launch calls, that errors is surfaced as a wait error.", func() {
			swarming.setCallback(func() {
				swarming.setError(fmt.Errorf("foo error"))
			})
			err := run.LaunchAndWait(ctx, swarming, gf)
			So(err.Error(), ShouldContainSubstring, "wait for task")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})
	})
}

func TestTaskURL(t *testing.T) {
	Convey("Given a single enumerated test running to completion, its task URL is well formed.", t, func() {
		ctx := context.Background()
		swarming_service := "https://foo.bar.com/"
		swarming := newFakeSwarming(swarming_service)
		getter := newFakeGetter()
		gf := fakeGetterFactory(getter)

		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, basicParams(), basicConfig())
		run.LaunchAndWait(ctx, swarming, gf)

		resp := run.Response(swarming)
		So(resp.TaskResults, ShouldHaveLength, 1)
		taskURL := resp.TaskResults[0].TaskUrl
		So(taskURL, ShouldStartWith, swarming_service)
		So(taskURL, ShouldEndWith, "1")
	})
}

func TestIncompleteWait(t *testing.T) {
	Convey("Given a run that is cancelled while running, error and response reflect cancellation.", t, func() {
		ctx, cancel := context.WithCancel(context.Background())

		swarming := newFakeSwarming("")
		swarming.setTaskState(jsonrpc.TaskState_RUNNING)
		getter := newFakeGetter()
		gf := fakeGetterFactory(getter)

		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, basicParams(), basicConfig())

		wg := sync.WaitGroup{}
		wg.Add(1)
		var err error
		go func() {
			err = run.LaunchAndWait(ctx, swarming, gf)
			wg.Done()
		}()

		cancel()
		wg.Wait()

		So(err.Error(), ShouldContainSubstring, context.Canceled.Error())

		resp := run.Response(swarming)
		So(resp, ShouldNotBeNil)
		So(resp.TaskResults, ShouldHaveLength, 1)
		So(resp.TaskResults[0].State.LifeCycle, ShouldEqual, test_platform.TaskState_LIFE_CYCLE_RUNNING)
		// TODO(akeshet): Ensure that response either reflects the error or
		// has an incomplete flag, once that part of the response proto is
		// defined.
	})
}

func TestRequestArguments(t *testing.T) {
	Convey("Given a server test with autotest labels", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming("")
		getter := newFakeGetter()
		gf := fakeGetterFactory(getter)

		tests := []*build_api.AutotestTest{
			newTest("name1", false, &build_api.AutotestTaskDependency{Label: "cr50:pvt"}),
		}

		run := skylab.NewTaskSet(tests, basicParams(), basicConfig())
		run.LaunchAndWait(ctx, swarming, gf)

		Convey("the launched task request should have correct parameters.", func() {
			So(swarming.createCalls, ShouldHaveLength, 1)
			create := swarming.createCalls[0]
			So(create.TaskSlices, ShouldHaveLength, 2)

			So(create.Tags, ShouldContain, "luci-project:foo-luci-project")

			prefix := "log_location:"
			var logdogURL string
			matchingTags := 0
			for _, tag := range create.Tags {
				if strings.HasPrefix(tag, prefix) {
					matchingTags++
					So(tag, ShouldEndWith, "+/annotations")

					logdogURL = strings.TrimPrefix(tag, "log_location:")
				}
			}
			So(matchingTags, ShouldEqual, 1)
			So(logdogURL, ShouldStartWith, "logdog://foo-logdog-host/foo-luci-project/skylab/")
			So(logdogURL, ShouldEndWith, "/+/annotations")

			for i, slice := range create.TaskSlices {
				flatCommand := strings.Join(slice.Properties.Command, " ")

				So(flatCommand, ShouldContainSubstring, "-task-name name1")
				So(flatCommand, ShouldNotContainSubstring, "-client-test")

				// Logdog annotation url argument should match the associated tag's url.
				So(flatCommand, ShouldContainSubstring, "-logdog-annotation-url "+logdogURL)

				provisionArg := "-provision-labels cros-version:foo-build"
				if i == 0 {
					So(flatCommand, ShouldNotContainSubstring, provisionArg)
				} else {
					So(flatCommand, ShouldContainSubstring, provisionArg)
				}

				flatDimensions := make([]string, len(slice.Properties.Dimensions))
				for i, d := range slice.Properties.Dimensions {
					flatDimensions[i] = d.Key + ":" + d.Value
				}
				So(flatDimensions, ShouldContain, "label-cr50_phase:CR50_PHASE_PVT")
				So(flatDimensions, ShouldContain, "label-model:foo-model")
				So(flatDimensions, ShouldContain, "label-board:foo-board")
			}
		})
	})
}

func TestClientTestArg(t *testing.T) {
	Convey("Given a client test", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming("")

		tests := []*build_api.AutotestTest{newTest("name1", true)}

		run := skylab.NewTaskSet(tests, basicParams(), basicConfig())
		run.LaunchAndWait(ctx, swarming, fakeGetterFactory(newFakeGetter()))

		Convey("the launched task request should have correct parameters.", func() {
			So(swarming.createCalls, ShouldHaveLength, 1)
			create := swarming.createCalls[0]
			So(create.TaskSlices, ShouldHaveLength, 2)
			for _, slice := range create.TaskSlices {
				flatCommand := strings.Join(slice.Properties.Command, " ")
				So(flatCommand, ShouldContainSubstring, "-client-test")
			}
		})
	})
}
