// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming defines an interface for interacting with swarming.
package swarming

import (
	"context"

	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/libs/skylab/swarming"
)

// URLer defines an interface to turn task IDs into task URLs.
type URLer interface {
	GetTaskURL(taskID string) string
}

// Client defines an interface used to interact with a swarming service.
type Client interface {
	URLer
	BotExists(context.Context, []*swarming_api.SwarmingRpcsStringPair) (bool, error)
	CreateTask(context.Context, *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error)
	GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error)
	GetTaskOutputs(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskOutput, error)
}

// swarming.Client is the reference implementation of the Client interface.
var _ Client = &swarming.Client{}

// UnfinishedTaskStates indicate swarming states that correspond to non-final
// tasks.
var UnfinishedTaskStates = map[jsonrpc.TaskState]bool{
	jsonrpc.TaskState_PENDING: true,
	jsonrpc.TaskState_RUNNING: true,
}

// CompletedTaskStates indicate swarming states that correspond to final-tasks
// in which the task executed to completion.
var CompletedTaskStates = map[jsonrpc.TaskState]bool{
	jsonrpc.TaskState_COMPLETED: true,
}

// AsTaskState converts the string swarming task state into enum representation.
func AsTaskState(state string) (jsonrpc.TaskState, error) {
	val, ok := jsonrpc.TaskState_value[state]
	if !ok {
		return jsonrpc.TaskState_INVALID, errors.Reason("invalid task state %s", state).Err()
	}
	return jsonrpc.TaskState(val), nil
}
