// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"net/http"

	"go.chromium.org/luci/server/auth"

	"golang.org/x/net/context"

	admin "infra/tricium/api/admin/v1"
)

// ResultState contains the current status of a given task.
type ResultState int

const (
	Pending ResultState = iota
	Success
	Failure
)

// TriggerResult contains the return value of a Trigger call to a TaskServerAPI.
//
// One and only one of TaskId and BuildId should be populated.
// TaskId is the string representation of the ID of the triggered swarming task
// BuildId is the int64 representation of the ID of the triggered buildbucket build
type TriggerResult struct {
	TaskID  string
	BuildID int64
}

// CollectResult contains the return value of a Collect call to a TaskServerAPI.
//
// State is the current status of the task (can be PENDING, SUCCESS, or FAILURE)
// One and only one of IsolatedOutputHash and BuildbucketOutput should be populated.
// IsolatedOutputHash is the data value of a completed Swarming task.
// BuildbucketOutput is the data value of a completed Buildbucket build.
type CollectResult struct {
	State              ResultState
	IsolatedOutputHash string
	BuildbucketOutput  string
}

// TaskServerAPI specifies the Swarming service API.
type TaskServerAPI interface {
	// Trigger triggers a swarming task.
	//
	// The provided worker isolate is used for the task. At completion,
	// the swarming service will publish a message, including the provided
	// user data, to the worker completion pubsub topic.
	Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string, tags []string) (*TriggerResult, error)

	// Collect collects results for a swarming task with the provided ID.
	//
	// The task in question should be completed before this function is called and the
	// task should have output.
	Collect(c context.Context, serverURL, taskID string, buildID int64) (*CollectResult, error)
}

func getOAuthClient(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

// MockTaskServerAPI mocks the TaskServerAPI interface for testing.
var MockTaskServerAPI mockTaskServerAPI

type mockTaskServerAPI struct {
}

// Trigger is a mock function for the MockTaskServerAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockTaskServerAPI) Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string, tags []string) (*TriggerResult, error) {
	return &TriggerResult{TaskID: "mocktaskid"}, nil
}

// Collect is a mock function for the MockTaskServerAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockTaskServerAPI) Collect(c context.Context, serverURL, taskID string, buildID int64) (*CollectResult, error) {
	return &CollectResult{
		State:              Success,
		IsolatedOutputHash: "mockisolatedoutput",
	}, nil
}
