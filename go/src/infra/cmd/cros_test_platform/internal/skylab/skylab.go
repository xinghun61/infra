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
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/request"
)

// Run encapsulates the running state of an ExecuteRequest.
type Run struct {
	testRuns []*testRun
}

type testRun struct {
	test     *build_api.AutotestTest
	attempts []attempt
}

type attempt struct {
	taskID    string
	completed bool
}

// Swarming defines an interface used to interact with a swarming service.
// It is implemented by infra/libs/skylab/swarming.Client
type Swarming interface {
	CreateTask(context.Context, *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error)
	GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error)
}

// NewRun creates a new Run.
func NewRun(tests []*build_api.AutotestTest) *Run {
	testRuns := make([]*testRun, len(tests))
	for i, test := range tests {
		testRuns[i] = &testRun{test: test}
	}
	return &Run{testRuns}
}

// LaunchAndWait launches a skylab execution and waits for it to complete,
// polling for new results periodically (TODO(akeshet): and retrying tests that
// need retry, based on retry policy).
//
// If the supplied context is cancelled prior to completion, or some other error
// is encountered, this method returns whatever partial execution response
// was visible to it prior to that error.
func (r *Run) LaunchAndWait(ctx context.Context, swarming Swarming) (*steps.ExecuteResponse, error) {
	if err := r.launch(ctx, swarming); err != nil {
		return r.response(), err
	}

	return r.wait(ctx, swarming)
}

func (r *Run) launch(ctx context.Context, swarming Swarming) error {
	for _, testRun := range r.testRuns {
		// TODO(akeshet): These request args don't include any of the actual
		// test details yet. Fix this, and use correct args.
		req, err := request.New(request.Args{})
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

func (r *Run) wait(ctx context.Context, swarming Swarming) (*steps.ExecuteResponse, error) {
	for {
		complete, err := r.tick(ctx, swarming)
		if complete || err != nil {
			return r.response(), err
		}

		select {
		case <-ctx.Done():
			return r.response(), errors.Annotate(ctx.Err(), "wait for tests").Err()
		case <-time.After(15 * time.Second):
		}
	}
}

func (r *Run) tick(ctx context.Context, swarming Swarming) (complete bool, err error) {
	complete = true

	for _, testRun := range r.testRuns {
		attempt := testRun.attempts[len(testRun.attempts)-1]
		if attempt.completed {
			continue
		}

		results, err := swarming.GetResults(ctx, []string{attempt.taskID})
		if err != nil {
			return false, errors.Annotate(err, "wait for tests").Err()
		}

		result, err := unpackResultForAttempt(results, attempt)
		if err != nil {
			return false, errors.Annotate(err, "wait for tests").Err()
		}

		// TODO(akeshet): Respect actual completed statuses.
		if result.State == "COMPLETED" {
			attempt.completed = true
			continue
		}

		// At least one task is not complete.
		complete = false
	}

	return complete, nil
}

func unpackResultForAttempt(results []*swarming_api.SwarmingRpcsTaskResult, a attempt) (*swarming_api.SwarmingRpcsTaskResult, error) {
	if len(results) != 1 {
		return nil, errors.Reason("expected 1 result for task id %s, got %d", a.taskID, len(results)).Err()
	}

	result := results[0]
	if result.TaskId != a.taskID {
		return nil, errors.Reason("expected result for task id %s, got %s", a.taskID, result.TaskId).Err()
	}

	return result, nil
}

func (r *Run) response() *steps.ExecuteResponse {
	resp := &steps.ExecuteResponse{}
	for _, test := range r.testRuns {
		for _, attempt := range test.attempts {
			resp.TaskResults = append(resp.TaskResults, &steps.ExecuteResponse_TaskResult{
				Name:   test.test.Name,
				TaskId: attempt.taskID,
				// TODO(akeshet): Determine correct taskURL. This requires knowing
				// which swarming instance was used.
				TaskUrl: "taskurl_placeholder",
			})
		}
	}
	return resp
}
