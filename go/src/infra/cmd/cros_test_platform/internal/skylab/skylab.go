// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package skylab implements logic necessary for Skylab execution of an
// ExecuteRequest.
package skylab

import (
	"context"
	"time"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
	"infra/libs/skylab/request"
	"infra/libs/skylab/worker"
)

// TaskSet encapsulates the running state of a set of tasks, to satisfy
// a Skylab Execution.
type TaskSet struct {
	testRuns []*testRun
	params   *test_platform.Request_Params
}

// unfinishedTaskStates indicate swarming states that correspond to non-final
// tasks.
var unfinishedTaskStates = map[jsonrpc.TaskState]bool{
	jsonrpc.TaskState_PENDING: true,
	jsonrpc.TaskState_RUNNING: true,
}

type testRun struct {
	test     *build_api.AutotestTest
	attempts []attempt
}

type attempt struct {
	taskID    string
	completed bool
	state     jsonrpc.TaskState
}

// Swarming defines an interface used to interact with a swarming service.
// It is implemented by infra/libs/skylab/swarming.Client
type Swarming interface {
	CreateTask(context.Context, *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error)
	GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error)
	GetTaskURL(taskID string) string
}

// NewTaskSet creates a new TaskSet.
func NewTaskSet(tests []*build_api.AutotestTest, params *test_platform.Request_Params) *TaskSet {
	testRuns := make([]*testRun, len(tests))
	for i, test := range tests {
		testRuns[i] = &testRun{test: test}
	}
	return &TaskSet{
		testRuns: testRuns,
		params:   params,
	}
}

// LaunchAndWait launches a skylab execution and waits for it to complete,
// polling for new results periodically (TODO(akeshet): and retrying tests that
// need retry, based on retry policy).
//
// If the supplied context is cancelled prior to completion, or some other error
// is encountered, this method returns whatever partial execution response
// was visible to it prior to that error.
func (r *TaskSet) LaunchAndWait(ctx context.Context, swarming Swarming) error {
	if err := r.launch(ctx, swarming); err != nil {
		return err
	}

	return r.wait(ctx, swarming)
}

func (r *TaskSet) launch(ctx context.Context, swarming Swarming) error {
	for _, testRun := range r.testRuns {
		t := testRun.test
		// TODO(akeshet): Run cmd.Config() with correct environment.
		cmd := &worker.Command{TaskName: t.Name}

		args := request.Args{
			Cmd:               *cmd,
			SchedulableLabels: toInventoryLabels(t.Dependencies),
			// TODO(akeshet): Determine parent task ID correctly.
			ParentTaskID: "",
			// TODO(akeshet): Determine priority correctly.
			Priority: 0,
			// TODO(akeshet): Determine provisionable dimensions correctly.
			ProvisionableDimensions: nil,
			// TODO(akeshet): Determine tags correctly.
			Tags: nil,
			// TODO(akeshet): Determine timeout correctly.
			TimeoutMins: 0,
		}
		req, err := request.New(args)
		if err != nil {
			return errors.Annotate(err, "launch test").Err()
		}

		resp, err := swarming.CreateTask(ctx, req)
		if err != nil {
			return errors.Annotate(err, "launch test").Err()
		}

		testRun.attempts = append(testRun.attempts, attempt{taskID: resp.TaskId})
	}
	return nil
}

func (r *TaskSet) wait(ctx context.Context, swarming Swarming) error {
	for {
		complete, err := r.tick(ctx, swarming)
		if complete || err != nil {
			return err
		}

		select {
		case <-ctx.Done():
			return errors.Annotate(ctx.Err(), "wait for tests").Err()
		case <-clock.After(ctx, 15*time.Second):
		}
	}
}

func (r *TaskSet) tick(ctx context.Context, swarming Swarming) (complete bool, err error) {
	complete = true

	for _, testRun := range r.testRuns {
		attempt := &testRun.attempts[len(testRun.attempts)-1]
		if attempt.completed {
			continue
		}

		results, err := swarming.GetResults(ctx, []string{attempt.taskID})
		if err != nil {
			return false, errors.Annotate(err, "wait for tests").Err()
		}

		result, err := unpackResult(results, attempt.taskID)
		if err != nil {
			return false, errors.Annotate(err, "wait for tests").Err()
		}

		state, err := unpackTaskState(result.State)
		if err != nil {
			return false, errors.Annotate(err, "wait for tests").Err()
		}
		attempt.state = state

		if !unfinishedTaskStates[state] {
			attempt.completed = true
			continue
		}

		// At least one task is not complete.
		complete = false
	}

	return complete, nil
}

func toInventoryLabels(deps []*build_api.AutotestTaskDependency) inventory.SchedulableLabels {
	flatDims := make([]string, len(deps))
	for i, dep := range deps {
		flatDims[i] = dep.Label
	}
	return *labels.Revert(flatDims)
}

func unpackResult(results []*swarming_api.SwarmingRpcsTaskResult, taskID string) (*swarming_api.SwarmingRpcsTaskResult, error) {
	if len(results) != 1 {
		return nil, errors.Reason("expected 1 result for task id %s, got %d", taskID, len(results)).Err()
	}

	result := results[0]
	if result.TaskId != taskID {
		return nil, errors.Reason("expected result for task id %s, got %s", taskID, result.TaskId).Err()
	}

	return result, nil
}

func unpackTaskState(state string) (jsonrpc.TaskState, error) {
	val, ok := jsonrpc.TaskState_value[state]
	if !ok {
		return jsonrpc.TaskState_INVALID, errors.Reason("invalid task state %s", state).Err()
	}
	return jsonrpc.TaskState(val), nil
}

var taskStateToLifeCycle = map[jsonrpc.TaskState]test_platform.TaskState_LifeCycle{
	jsonrpc.TaskState_BOT_DIED:  test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_CANCELED:  test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_COMPLETED: test_platform.TaskState_LIFE_CYCLE_COMPLETED,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_EXPIRED:     test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_KILLED:      test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_NO_RESOURCE: test_platform.TaskState_LIFE_CYCLE_REJECTED,
	jsonrpc.TaskState_PENDING:     test_platform.TaskState_LIFE_CYCLE_PENDING,
	jsonrpc.TaskState_RUNNING:     test_platform.TaskState_LIFE_CYCLE_RUNNING,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_TIMED_OUT: test_platform.TaskState_LIFE_CYCLE_ABORTED,
}

// Response constructs a response based on the current state of the
// TaskSet.
func (r *TaskSet) Response(swarming Swarming) *steps.ExecuteResponse {
	resp := &steps.ExecuteResponse{}
	for _, test := range r.testRuns {
		for _, attempt := range test.attempts {
			resp.TaskResults = append(resp.TaskResults, &steps.ExecuteResponse_TaskResult{
				Name: test.test.Name,
				State: &test_platform.TaskState{
					LifeCycle: taskStateToLifeCycle[attempt.state],
					// TODO(akeshet): Determine a way to extract and identify
					// test verdicts.
					Verdict: test_platform.TaskState_VERDICT_NO_VERDICT,
				},
				TaskId:  attempt.taskID,
				TaskUrl: swarming.GetTaskURL(attempt.taskID),
			})
		}
	}
	return resp
}
