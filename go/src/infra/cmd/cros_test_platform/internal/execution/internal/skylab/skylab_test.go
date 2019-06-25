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

	. "github.com/smartystreets/goconvey/convey"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/execution/internal/skylab"
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
	results := make([]*swarming_api.SwarmingRpcsTaskResult, len(IDs))
	for i, taskID := range IDs {
		results[i] = &swarming_api.SwarmingRpcsTaskResult{
			TaskId: taskID,
			State:  jsonrpc.TaskState_name[int32(f.nextState)],
		}
	}
	return results, nil
}

func (f *fakeSwarming) GetTaskURL(taskID string) string {
	// Note: this is not the true swarming task URL schema.
	return f.server + "/task=" + taskID
}

// setTaskState causes this fake to start returning the given state of all future
func (f *fakeSwarming) setTaskState(state jsonrpc.TaskState) {
	f.nextState = state
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
	}
}

func newTest(name string, client bool, labels ...string) *build_api.AutotestTest {
	ee := build_api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER
	if client {
		ee = build_api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT
	}
	deps := make([]*build_api.AutotestTaskDependency, len(labels))
	for i, lab := range labels {
		deps[i] = &build_api.AutotestTaskDependency{Label: lab}
	}
	return &build_api.AutotestTest{Name: name, ExecutionEnvironment: ee, Dependencies: deps}
}

func TestLaunchAndWaitTest(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := newFakeSwarming("")

		var tests []*build_api.AutotestTest
		tests = append(tests, newTest("", false), newTest("", true))

		Convey("when running a skylab execution", func() {
			run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})

			err := run.LaunchAndWait(ctx, swarming)
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

func TestServiceError(t *testing.T) {
	Convey("Given a single enumerated test", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming("")

		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})

		Convey("when the swarming service immediately returns errors, that error is surfaced as a launch error.", func() {
			swarming.setError(fmt.Errorf("foo error"))
			err := run.LaunchAndWait(ctx, swarming)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "launch test")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})

		Convey("when the swarming service starts returning errors after the initial launch calls, that errors is surfaced as a wait error.", func() {
			swarming.setCallback(func() {
				swarming.setError(fmt.Errorf("foo error"))
			})
			err := run.LaunchAndWait(ctx, swarming)
			So(err.Error(), ShouldContainSubstring, "wait for tests")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})
	})
}

func TestTaskURL(t *testing.T) {
	Convey("Given a single enumerated test running to completion, its task URL is well formed.", t, func() {
		ctx := context.Background()
		swarming_service := "https://foo.bar.com/"
		swarming := newFakeSwarming(swarming_service)
		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})
		run.LaunchAndWait(ctx, swarming)

		resp := run.Response(swarming)
		So(resp.TaskResults, ShouldHaveLength, 1)
		taskURL := resp.TaskResults[0].TaskUrl
		taskID := resp.TaskResults[0].TaskId
		So(taskURL, ShouldStartWith, swarming_service)
		So(taskURL, ShouldEndWith, taskID)
	})
}

func TestIncompleteWait(t *testing.T) {
	Convey("Given a run that is cancelled while running, error and response reflect cancellation.", t, func() {
		ctx, cancel := context.WithCancel(context.Background())

		swarming := newFakeSwarming("")
		swarming.setTaskState(jsonrpc.TaskState_RUNNING)

		tests := []*build_api.AutotestTest{newTest("", false)}
		run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})

		wg := sync.WaitGroup{}
		wg.Add(1)
		var err error
		go func() {
			err = run.LaunchAndWait(ctx, swarming)
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

		tests := []*build_api.AutotestTest{
			newTest("name1", false, "board:foo_board", "model:foo_model"),
		}

		run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})
		run.LaunchAndWait(ctx, swarming)

		Convey("the launched task request should have correct parameters.", func() {
			So(swarming.createCalls, ShouldHaveLength, 1)
			create := swarming.createCalls[0]
			// TODO(akeshet): Add a provisionable label to the request and proper
			// provisionable label handling, at which point we will expect 2
			// slices here.
			So(create.TaskSlices, ShouldHaveLength, 1)

			slice := create.TaskSlices[0]
			flatCommand := strings.Join(slice.Properties.Command, " ")
			So(flatCommand, ShouldContainSubstring, "-task-name name1")
			So(flatCommand, ShouldNotContainSubstring, "-client-test")

			flatDimensions := make([]string, len(slice.Properties.Dimensions))
			for i, d := range slice.Properties.Dimensions {
				flatDimensions[i] = d.Key + ":" + d.Value
			}
			So(flatDimensions, ShouldContain, "label-board:foo_board")
			So(flatDimensions, ShouldContain, "label-model:foo_model")
		})
	})
}

func TestClientTestArg(t *testing.T) {
	Convey("Given a client test", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming("")

		tests := []*build_api.AutotestTest{
			newTest("name1", true, "board:foo_board", "model:foo_model"),
		}

		run := skylab.NewTaskSet(tests, &test_platform.Request_Params{})
		run.LaunchAndWait(ctx, swarming)

		Convey("the launched task request should have correct parameters.", func() {
			So(swarming.createCalls, ShouldHaveLength, 1)
			create := swarming.createCalls[0]
			So(create.TaskSlices, ShouldHaveLength, 1)
			slice := create.TaskSlices[0]
			flatCommand := strings.Join(slice.Properties.Command, " ")
			So(flatCommand, ShouldContainSubstring, "-client-test")
		})
	})
}
