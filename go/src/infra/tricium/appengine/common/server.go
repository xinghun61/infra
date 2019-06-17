// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"net/http"

	"go.chromium.org/luci/server/auth"

	admin "infra/tricium/api/admin/v1"
)

// ResultState contains the current status of a given task.
type ResultState int

// Constants for describing the result of a task.
const (
	Pending ResultState = iota
	Success
	Failure
)

// PatchDetails contains information about the Gerrit and Gitiles patchset.
type PatchDetails struct {
	GitilesHost    string
	GitilesProject string
	GerritHost     string
	GerritProject  string
	GerritChange   string
	GerritCl       string
	GerritPatch    string
}

// TriggerParameters contains the parameters for a Trigger call to a TaskServerAPI.
type TriggerParameters struct {
	Server           string
	IsolateServerURL string
	Worker           *admin.Worker
	WorkerIsolate    string
	PubsubUserdata   string
	Tags             []string
	Patch            PatchDetails
}

// TriggerResult contains the return value of a Trigger call to a TaskServerAPI.
//
// One and only one of TaskID and BuildID should be populated.
// TaskID is the string representation of the ID of the triggered swarming task
// BuildID is the int64 representation of the ID of the triggered buildbucket build
type TriggerResult struct {
	TaskID  string
	BuildID int64
}

// CollectParameters contains the parameters for a Collect call to a TaskServerAPI.
//
// One and only one of TaskID and BuildID should be populated.
// TaskID is the string representation of the ID of the collected swarming task
// BuildID is the int64 representation of the ID of the collected buildbucket build
type CollectParameters struct {
	Server  string
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
	IsolatedNamespace  string
	BuildbucketOutput  string
}

// TaskServerAPI specifies the Swarming service API.
type TaskServerAPI interface {
	// Trigger triggers a swarming task.
	//
	// The provided worker isolate is used for the task. At completion,
	// the swarming service will publish a message, including the provided
	// user data, to the worker completion pubsub topic.
	Trigger(c context.Context, params *TriggerParameters) (*TriggerResult, error)

	// Collect collects results for a swarming task with the provided ID.
	//
	// The task in question should be completed before this function is called and the
	// task should have output.
	Collect(c context.Context, params *CollectParameters) (*CollectResult, error)
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
func (mockTaskServerAPI) Trigger(c context.Context, params *TriggerParameters) (*TriggerResult, error) {
	return &TriggerResult{TaskID: "mocktaskid"}, nil
}

// Collect is a mock function for the MockTaskServerAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockTaskServerAPI) Collect(c context.Context, params *CollectParameters) (*CollectResult, error) {
	return &CollectResult{
		State:              Success,
		IsolatedOutputHash: "mockisolatedoutput",
		IsolatedNamespace:  "mockisolatednamespace",
	}, nil
}
