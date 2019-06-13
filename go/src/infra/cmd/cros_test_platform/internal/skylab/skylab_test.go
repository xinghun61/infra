// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab_test

import (
	"context"
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	chromite "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/skylab"
)

// fakeSwarming implements skylab.Swarming
type fakeSwarming struct {
	nextID      int
	nextState   jsonrpc.TaskState
	nextError   error
	callback    func()
	createCalls int
	getCalls    int
}

func (f *fakeSwarming) CreateTask(ctx context.Context, req *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error) {
	defer f.callback()
	f.nextID++
	f.createCalls++
	if f.nextError != nil {
		return nil, f.nextError
	}
	resp := &swarming_api.SwarmingRpcsTaskRequestMetadata{TaskId: fmt.Sprintf("task%d", f.nextID)}
	return resp, nil
}

func (f *fakeSwarming) GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	defer f.callback()
	f.getCalls++
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

// setTaskState causes this fake to start returning the given state of all future
// GetResults calls.
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

func newFakeSwarming() *fakeSwarming {
	return &fakeSwarming{
		nextState: jsonrpc.TaskState_COMPLETED,
		callback:  func() {},
	}
}

func TestLaunchAndWaitSingleTest(t *testing.T) {
	Convey("Given two enumerated test", t, func() {
		ctx := context.Background()

		swarming := newFakeSwarming()

		var tests []*chromite.AutotestTest
		tests = append(tests, &chromite.AutotestTest{}, &chromite.AutotestTest{})

		Convey("when running a skylab execution", func() {
			run := skylab.NewRun(tests)

			resp, err := run.LaunchAndWait(ctx, swarming)
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)

			Convey("then results for all tests are reflected.", func() {
				So(resp.TaskResults, ShouldHaveLength, 2)
			})
			Convey("then the expected number of external swarming calls are made.", func() {
				So(swarming.getCalls, ShouldEqual, 2)
				So(swarming.createCalls, ShouldEqual, 2)
			})
		})
	})
}

func TestServiceError(t *testing.T) {
	Convey("Given a single enumerated test", t, func() {
		ctx := context.Background()
		swarming := newFakeSwarming()

		tests := []*chromite.AutotestTest{{}}
		run := skylab.NewRun(tests)

		Convey("when the swarming service immediately returns errors, that error is surfaced as a launch error.", func() {
			swarming.setError(fmt.Errorf("foo error"))
			_, err := run.LaunchAndWait(ctx, swarming)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "launch test")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})

		Convey("when the swarming service starts returning errors after the initial launch calls, that errors is surfaced as a wait error.", func() {
			swarming.setCallback(func() {
				swarming.setError(fmt.Errorf("foo error"))
			})
			_, err := run.LaunchAndWait(ctx, swarming)
			So(err.Error(), ShouldContainSubstring, "wait for tests")
			So(err.Error(), ShouldContainSubstring, "foo error")
		})
	})
}
